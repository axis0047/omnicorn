-module(omn_worker).
-behaviour(gen_server).

%% API
-export([start_link/2, call_python/3]).

%% GenServer Callbacks
-export([init/1, handle_call/3, handle_cast/2, handle_info/2, terminate/2, code_change/3]).

-record(state, {
    log_port :: port(),    % Stdin/Stdout/Stderr for logging only
    data_socket :: port(), % The UDS Socket for data
    listener :: port(),    % The UDS Listener
    socket_path :: list(),
    worker_id :: integer(),
    requests = #{} :: map()
}).

start_link(AppModule, Id) ->
    gen_server:start_link(?MODULE, [AppModule, Id],[]).

call_python(Pid, Type, Payload) ->
    TimeoutStr = os:getenv("OMNICORN_TIMEOUT", "5000"),
    Timeout = list_to_integer(TimeoutStr),
    try gen_server:call(Pid, {request, Type, Payload}, Timeout) of
        Result -> {ok, Result}
    catch
        exit:{timeout, _} -> {error, timeout};
        exit:Reason -> {error, Reason}
    end.

%% ===================================================================
%% GenServer Implementation
%% ===================================================================

init([AppModule, Id]) ->
    process_flag(trap_exit, true),

    SocketPath = lists:flatten(io_lib:format("/tmp/omnicorn_~p_~p.sock",[os:getpid(), Id])),
    file:delete(SocketPath),

    case gen_tcp:listen(0,[{ifaddr, {local, SocketPath}}, {mode, binary}, {packet, 4}, {active, true}]) of
        {ok, LSock} ->
            Cmd = "python3 -m omnicorn.worker " ++ binary_to_list(AppModule),
            Port = open_port({spawn, Cmd},[
                binary,
                exit_status,
                use_stdio,
                stderr_to_stdout,
                {env,[{"OMNICORN_SOCK", SocketPath}]}
            ]),

            %% We use a custom wait loop so we can print Python syntax/import errors to the console
            %% in real-time if Python crashes during boot! (50 retries * 100ms = 5000ms timeout)
            case wait_for_connection(LSock, Port, 50) of
                {ok, DataSocket} ->
                    {ok, #state{
                        log_port = Port,
                        data_socket = DataSocket,
                        listener = LSock,
                        socket_path = SocketPath,
                        worker_id = Id
                    }};
                {error, Reason} ->
                    io:format("🔥 Python Worker ~p failed to boot: ~p~n", [Id, Reason]),
                    {stop, Reason}
            end;

        {error, Reason} ->
            io:format("Failed to create UDS listener: ~p~n",[Reason]),
            {stop, socket_create_error}
    end.

%% Helper function to poll the socket while reading Python's boot logs
wait_for_connection(LSock, Port, Retries) when Retries > 0 ->
    case gen_tcp:accept(LSock, 100) of
        {ok, DataSocket} ->
            {ok, DataSocket};
        {error, timeout} ->
            %% Check if Python printed an error or died while we were waiting
            receive
                {Port, {data, LogLine}} ->
                    io:format("[PYTHON-BOOT] ~s", [LogLine]),
                    wait_for_connection(LSock, Port, Retries - 1);
                {Port, {exit_status, Status}} ->
                    io:format("🔥 Python process died immediately with status ~p~n", [Status]),
                    {error, python_crashed_on_boot}
            after 0 ->
                %% No logs, just keep waiting
                wait_for_connection(LSock, Port, Retries - 1)
            end;
        {error, Reason} ->
            {error, Reason}
    end;
wait_for_connection(_, _, 0) ->
    {error, connection_timeout}.

handle_call({request, Type, Payload}, From, State) ->
    ReqId = erlang:phash2(erlang:make_ref()),
    Message = #{<<"id">> => ReqId, <<"type">> => Type, <<"payload">> => Payload},

    Packet = term_to_binary(Message),
    gen_tcp:send(State#state.data_socket, Packet),

    NewReqs = maps:put(ReqId, From, State#state.requests),
    {noreply, State#state{requests = NewReqs}}.

handle_cast(_Msg, State) ->
    {noreply, State}.

%% --- DATA PLANE (UDS Socket) ---
handle_info({tcp, _Socket, Data}, State) ->
    try binary_to_term(Data) of
        Decoded ->
            %% 1. Is this a Worker Handshake?
            case maps:get(<<"status">>, Decoded, undefined) of
                <<"ready">> ->
                    omn_router:checkin_worker(self()),
                    {noreply, State};
                _ ->
                    %% 2. Is this an RPC call from Python to Erlang?
                    case maps:get(<<"type">>, Decoded, undefined) of
                        <<"ets_get">> ->
                            Payload = maps:get(<<"payload">>, Decoded),
                            Key = maps:get(<<"key">>, Payload),
                            ReqId = maps:get(<<"id">>, Decoded),
                            Now = erlang:system_time(millisecond),

                            %% ETS stores tuples: {Key, Value, ExpireAt}
                            Value = case ets:lookup(omnicorn_cache, Key) of[{Key, Val, ExpireAt}] ->
                                    if
                                        ExpireAt == 0 -> Val; %% No TTL
                                        Now =< ExpireAt -> Val; %% Valid TTL
                                        true ->
                                            ets:delete(omnicorn_cache, Key), %% Expired! Evict it.
                                            nil
                                    end;[] -> nil
                            end,

                            Packet = term_to_binary(#{<<"id">> => ReqId, <<"type">> => <<"ets_reply">>, <<"data">> => Value}),
                            gen_tcp:send(State#state.data_socket, Packet),
                            {noreply, State};

                        <<"ets_set">> ->
                            Payload = maps:get(<<"payload">>, Decoded),
                            Key = maps:get(<<"key">>, Payload),
                            Val = maps:get(<<"value">>, Payload),
                            TTL = maps:get(<<"ttl">>, Payload, 0), %% TTL in milliseconds
                            ReqId = maps:get(<<"id">>, Decoded),

                            ExpireAt = if TTL > 0 -> erlang:system_time(millisecond) + TTL; true -> 0 end,
                            ets:insert(omnicorn_cache, {Key, Val, ExpireAt}),

                            Packet = term_to_binary(#{<<"id">> => ReqId, <<"type">> => <<"ets_reply">>, <<"data">> => <<"ok">>}),
                            gen_tcp:send(State#state.data_socket, Packet),
                            {noreply, State};

                        <<"task_enqueue">> ->
                            Payload = maps:get(<<"payload">>, Decoded),
                            ReqId = maps:get(<<"id">>, Decoded),
                            %% Forward the payload to our Erlang Broker
                            omn_task_broker:enqueue(Payload),
                            %% Tell Python the defer() was successful
                            Packet = term_to_binary(#{<<"id">> => ReqId, <<"type">> => <<"ets_reply">>, <<"data">> => <<"queued">>}),
                            gen_tcp:send(State#state.data_socket, Packet),
                            {noreply, State};

                        <<"task_ack">> ->
                            TaskId = maps:get(<<"task_id">>, Decoded),
                            %% Delete the task from Mnesia/ETS because it succeeded!
                            mnesia:dirty_delete(omn_persistent_tasks, TaskId),
                            ets:delete(omnicorn_volatile_tasks, TaskId),
                            {noreply, State};

                        <<"task_fail">> ->
                            TaskId = maps:get(<<"task_id">>, Decoded),
                            Error = maps:get(<<"error">>, Decoded),
                            io:format("⚠️ Task ~p failed: ~p~n", [TaskId, Error]),
                            %% Here you would decrement retries in Mnesia and re-queue
                            {noreply, State};

                        <<"ets_delete">> ->
                            Payload = maps:get(<<"payload">>, Decoded),
                            Key = maps:get(<<"key">>, Payload),
                            ReqId = maps:get(<<"id">>, Decoded),

                            ets:delete(omnicorn_cache, Key),

                            Packet = term_to_binary(#{<<"id">> => ReqId, <<"type">> => <<"ets_reply">>, <<"data">> => <<"ok">>}),
                            gen_tcp:send(State#state.data_socket, Packet),
                            {noreply, State};

                        <<"ets_incr">> ->
                            Payload = maps:get(<<"payload">>, Decoded),
                            Key = maps:get(<<"key">>, Payload),
                            Amount = maps:get(<<"amount">>, Payload, 1),
                            ReqId = maps:get(<<"id">>, Decoded),

                            %% NATIVE SUPERPOWER: Lock-free atomic increment.
                            %% If key doesn't exist, it defaults to {Key, 0, 0} and increments from there!
                            NewVal = try ets:update_counter(omnicorn_cache, Key, {2, Amount}, {Key, 0, 0})
                                     catch _:_ -> nil end,

                            Packet = term_to_binary(#{<<"id">> => ReqId, <<"type">> => <<"ets_reply">>, <<"data">> => NewVal}),
                            gen_tcp:send(State#state.data_socket, Packet),
                            {noreply, State};

                        %% 3. Catch-all: This is a Response from Python returning to an Erlang HTTP/WS Request
                        _ ->
                            ReqId = maps:get(<<"id">>, Decoded),
                            ResultData = maps:get(<<"data">>, Decoded, #{}),
                            case maps:take(ReqId, State#state.requests) of
                                {From, NewReqs} ->
                                    gen_server:reply(From, ResultData),
                                    omn_router:checkin_worker(self()),
                                    {noreply, State#state{requests = NewReqs}};
                                error ->
                                    {noreply, State}
                            end
                    end
            end
    catch
        _:Err ->
            io:format("ETF Decode Error in Worker ~p: ~p~n",[State#state.worker_id, Err]),
            {noreply, State}
    end;

handle_info({tcp_closed, _Socket}, State) ->
    io:format("[Omnicorn] Worker ~p Data Connection Closed~n",[State#state.worker_id]),
    {stop, normal, State};

handle_info({Port, {data, LogLine}}, State = #state{log_port=Port}) ->
    io:format("[PYTHON-LOG ~p] ~s",[State#state.worker_id, LogLine]),
    {noreply, State};

handle_info({Port, {exit_status, Status}}, State = #state{log_port=Port}) ->
    io:format("[Omnicorn] Worker ~p OS Process Exit: ~p~n", [State#state.worker_id, Status]),
    {stop, python_died, State};

handle_info(Info, State) ->
    io:format("Unknown Info: ~p~n", [Info]),
    {noreply, State}.

terminate(_Reason, State) ->
    gen_tcp:close(State#state.data_socket),
    gen_tcp:close(State#state.listener),
    file:delete(State#state.socket_path),
    catch port_close(State#state.log_port),
    ok.

code_change(_OldVsn, State, _Extra) ->
    {ok, State}.

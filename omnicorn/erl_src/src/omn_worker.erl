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
    gen_server:start_link(?MODULE, [AppModule, Id], []).

call_python(Pid, Type, Payload) ->
    TimeoutStr = os:getenv("OMNICORN_TIMEOUT", "5000"),
    Timeout = list_to_integer(TimeoutStr),
    try gen_server:call(Pid, {request, Type, Payload}, Timeout)
    catch exit:{timeout, _} -> {error, timeout} end.

%% ===================================================================
%% GenServer Implementation
%% ===================================================================

init([AppModule, Id]) ->
    process_flag(trap_exit, true),

    %% 1. Create a unique UDS Path in /tmp
    SocketPath = lists:flatten(io_lib:format("/tmp/omnicorn_~p_~p.sock", [os:getpid(), Id])),
    file:delete(SocketPath), % Ensure it doesn't exist

    %% 2. Listen on UDS (Local Domain Socket)
    %% {packet, 4} automatically handles our 4-byte header logic!
    case gen_tcp:listen(0, [{ifaddr, {local, SocketPath}}, {mode, binary}, {packet, 4}, {active, true}]) of
        {ok, LSock} ->
            %% 3. Start Python, passing the socket path
            %% We do NOT use {packet, 4} on the Port anymore, it's just raw text logs now.
            Cmd = "python3 -m omnicorn.worker " ++ binary_to_list(AppModule),
            Port = open_port({spawn, Cmd}, [
                binary,
                exit_status,
                use_stdio,
                stderr_to_stdout,
                {env, [{"OMNICORN_SOCK", SocketPath}]}
            ]),

            %% 4. Wait for Python to connect (Blocking accept with timeout)
            %% In a high-scale system we would do async_accept, but for worker spawning
            %% a 5s block during init is acceptable safety.
            case gen_tcp:accept(LSock, 5000) of
                {ok, DataSocket} ->
                    {ok, #state{
                        log_port = Port,
                        data_socket = DataSocket,
                        listener = LSock,
                        socket_path = SocketPath,
                        worker_id = Id
                    }};
                {error, Reason} ->
                    io:format("Python failed to connect to UDS: ~p~n", [Reason]),
                    {stop, python_connection_timeout}
            end;

        {error, Reason} ->
            io:format("Failed to create UDS listener: ~p~n", [Reason]),
            {stop, socket_create_error}
    end.

handle_call({request, Type, Payload}, From, State) ->
    ReqId = erlang:phash2(erlang:make_ref()),
    Message = #{<<"id">> => ReqId, <<"type">> => Type, <<"payload">> => Payload},
    JsonPacket = jsone:encode(Message),

    %% Send via UDS Socket
    gen_tcp:send(State#state.data_socket, JsonPacket),

    NewReqs = maps:put(ReqId, From, State#state.requests),
    {noreply, State#state{requests = NewReqs}}.

handle_cast(_Msg, State) ->
    {noreply, State}.

%% --- DATA PLANE (UDS Socket) ---
handle_info({tcp, _Socket, Data}, State) ->
    try jsone:decode(Data) of
        Decoded ->
            case maps:get(<<"status">>, Decoded, undefined) of
                <<"ready">> ->
                    omn_router:checkin_worker(self()),
                    {noreply, State};
                _ ->
                    ReqId = maps:get(<<"id">>, Decoded),
                    ResultData = maps:get(<<"data">>, Decoded),
                    case maps:take(ReqId, State#state.requests) of
                        {From, NewReqs} ->
                            gen_server:reply(From, ResultData),
                            omn_router:checkin_worker(self()),
                            {noreply, State#state{requests = NewReqs}};
                        error ->
                            {noreply, State}
                    end
            end
    catch
        _:_ ->
            io:format("JSON Decode Error in Worker ~p~n", [State#state.worker_id]),
            {noreply, State}
    end;

handle_info({tcp_closed, _Socket}, State) ->
    io:format("[Omnicorn] Worker ~p Data Connection Closed~n", [State#state.worker_id]),
    {stop, normal, State};

%% --- CONTROL PLANE (Logging from Python Stdout) ---
handle_info({Port, {data, LogLine}}, State = #state{log_port=Port}) ->
    %% Python print() statements land here. We just log them.
    io:format("[PYTHON-LOG ~p] ~s", [State#state.worker_id, LogLine]),
    {noreply, State};

handle_info({Port, {exit_status, Status}}, State = #state{log_port=Port}) ->
    io:format("[Omnicorn] Worker ~p OS Process Exit: ~p~n", [State#state.worker_id, Status]),
    {stop, python_died, State};

handle_info(Info, State) ->
    io:format("Unknown Info: ~p~n", [Info]),
    {noreply, State}.

terminate(_Reason, State) ->
    %% Clean up resources
    gen_tcp:close(State#state.data_socket),
    gen_tcp:close(State#state.listener),
    file:delete(State#state.socket_path),
    catch port_close(State#state.log_port),
    ok.

code_change(_OldVsn, State, _Extra) ->
    {ok, State}.

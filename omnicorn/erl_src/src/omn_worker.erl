-module(omn_worker).
-behaviour(gen_server).

%% API
-export([start_link/2, call_python/3]).

%% GenServer Callbacks
-export([init/1, handle_call/3, handle_cast/2, handle_info/2, terminate/2, code_change/3]).

-record(state, {
    port :: port(),
    worker_id :: integer(),
    requests = #{} :: map() % Map of ReqId -> ClientFrom
}).

start_link(AppModule, Id) ->
    gen_server:start_link(?MODULE, [AppModule, Id], []).

call_python(Pid, Type, Payload) ->
    %% 5-second timeout protection
    try gen_server:call(Pid, {request, Type, Payload}, 5000)
    catch
        exit:{timeout, _} -> {error, timeout}
    end.

%% ===================================================================
%% GenServer Implementation
%% ===================================================================

init([AppModule, Id]) ->
    process_flag(trap_exit, true),

    %% Start Python Process
    %% {packet, 4}: Erlang handles the 4-byte length header automatically
    Command = "python3 -m omnicorn.worker " ++ binary_to_list(AppModule),
    Port = open_port({spawn, Command}, [
        {packet, 4},
        binary,
        exit_status,
        use_stdio,
        stderr_to_stdout
    ]),

    %% NOTE: We do NOT register with the router yet.
    %% We wait for Python to send {"status": "ready"} in handle_info.

    {ok, #state{port = Port, worker_id = Id}}.

handle_call({request, Type, Payload}, From, State) ->
    %% 1. Generate Unique ID
    ReqId = erlang:phash2(erlang:make_ref()),

    %% 2. Encode to JSON
    Message = #{
        <<"id">> => ReqId,
        <<"type">> => Type,
        <<"payload">> => Payload
    },
    JsonPacket = jsone:encode(Message),

    %% 3. Send to Python
    port_command(State#state.port, JsonPacket),

    %% 4. Store sender info to reply later
    NewReqs = maps:put(ReqId, From, State#state.requests),
    {noreply, State#state{requests = NewReqs}}.

handle_cast(_Msg, State) ->
    {noreply, State}.

%% HANDLE RESPONSES FROM PYTHON
handle_info({Port, {data, Data}}, State = #state{port=Port}) ->
    try jsone:decode(Data) of
        Decoded ->
            %% --- FIX START: Check for Handshake vs Response ---
            case maps:get(<<"status">>, Decoded, undefined) of
                <<"ready">> ->
                    %% Python is alive and modules are loaded.
                    %% NOW we tell the router we are ready for traffic.
                    omn_router:checkin_worker(self()),
                    {noreply, State};

                _ ->
                    %% Standard Request Response
                    ReqId = maps:get(<<"id">>, Decoded),
                    ResultData = maps:get(<<"data">>, Decoded),

                    case maps:take(ReqId, State#state.requests) of
                        {From, NewReqs} ->
                            gen_server:reply(From, ResultData),
                            %% Return worker to pool for next request
                            omn_router:checkin_worker(self()),
                            {noreply, State#state{requests = NewReqs}};
                        error ->
                            io:format("[Omnicorn] Worker ~p: Orphan response ID ~p~n", [State#state.worker_id, ReqId]),
                            {noreply, State}
                    end
            end
            %% --- FIX END ---
    catch
        _:Error ->
            io:format("[Omnicorn] Worker ~p decode error: ~p. Data: ~p~n", [State#state.worker_id, Error, Data]),
            {noreply, State}
    end;

handle_info({Port, {exit_status, Status}}, State = #state{port=Port}) ->
    io:format("[Omnicorn] Worker ~p CRASHED. Exit Status: ~p~n", [State#state.worker_id, Status]),
    {stop, python_process_died, State};

handle_info(Info, State) ->
    io:format("[Omnicorn] Worker ~p received unexpected info: ~p~n", [State#state.worker_id, Info]),
    {noreply, State}.

terminate(_Reason, #state{port=Port}) ->
    port_close(Port),
    ok.

code_change(_OldVsn, State, _Extra) ->
    {ok, State}.

-module(omn_worker).
-behaviour(gen_server).
-export([start_link/2, call_python/3, send_async/2]).
-export([init/1, handle_call/3, handle_cast/2, handle_info/2, terminate/2, code_change/3]).

-record(state, {log_port, data_socket, listener, path, id, reqs = #{}}).

start_link(App, Id) ->
    gen_server:start_link(?MODULE, [App, Id],[]).

call_python(Pid, Type, P) ->
    try gen_server:call(Pid, {req, Type, P}, 10000) of
        R -> {ok, R}
    catch
        _:_ -> {error, timeout}
    end.

send_async(Pid, Msg) ->
    gen_server:cast(Pid, {async, Msg}).

init([App, Id]) ->
    process_flag(trap_exit, true),
    Path = lists:flatten(io_lib:format("/tmp/omnicorn_~p_~p.sock", [os:getpid(), Id])),
    file:delete(Path),
    case gen_tcp:listen(0,[{ifaddr, {local, Path}}, {mode, binary}, {packet, 4}, {active, true}]) of
        {ok, LSock} ->
            Cmd = "python3 -m omnicorn.worker " ++ binary_to_list(App),
            Port = open_port({spawn, Cmd},[binary, exit_status, use_stdio, stderr_to_stdout, {env, [{"OMNICORN_SOCK", Path}]}]),
            case wait_conn(LSock, Port, 50) of
                {ok, DS} -> {ok, #state{log_port=Port, data_socket=DS, listener=LSock, path=Path, id=Id}};
                Err -> {stop, Err}
            end;
        Err -> {stop, Err}
    end.

wait_conn(LSock, Port, R) when R > 0 ->
    case gen_tcp:accept(LSock, 100) of
        {ok, DS} -> {ok, DS};
        {error, timeout} ->
            receive
                {Port, {data, L}} -> io:format("[PY-BOOT] ~s",[L]), wait_conn(LSock, Port, R-1);
                {Port, {exit_status, _}} -> {error, died}
            after 0 ->
                wait_conn(LSock, Port, R-1)
            end
    end;
wait_conn(_, _, 0) -> {error, timeout}.

handle_call({req, Type, P}, From, S) ->
    ReqId = erlang:phash2(erlang:make_ref()),
    gen_tcp:send(S#state.data_socket, term_to_binary(#{<<"id">> => ReqId, <<"type">> => Type, <<"payload">> => P})),
    {noreply, S#state{reqs = maps:put(ReqId, From, S#state.reqs)}};
handle_call(_, _, S) ->
    {reply, ok, S}.

handle_cast({async, Msg}, S) ->
    gen_tcp:send(S#state.data_socket, term_to_binary(Msg)),
    {noreply, S};
handle_cast(_, S) ->
    {noreply, S}.

handle_info({tcp, _, Data}, S) ->
    try binary_to_term(Data) of
        D ->
            case maps:get(<<"type">>, D, undefined) of
                <<"ets_get">> ->
                    P = maps:get(<<"payload">>, D),
                    V = case ets:lookup(omnicorn_cache, maps:get(<<"key">>, P)) of[{_, Val, 0}] -> Val;[] -> nil end,
                    gen_tcp:send(S#state.data_socket, term_to_binary(#{<<"id">> => maps:get(<<"id">>, D), <<"type">> => <<"ets_reply">>, <<"data">> => V})),
                    {noreply, S};

                <<"ets_set">> ->
                    P = maps:get(<<"payload">>, D),
                    ets:insert(omnicorn_cache, {maps:get(<<"key">>, P), maps:get(<<"value">>, P), maps:get(<<"ttl">>, P)}),
                    gen_tcp:send(S#state.data_socket, term_to_binary(#{<<"id">> => maps:get(<<"id">>, D), <<"type">> => <<"ets_reply">>, <<"data">> => <<"ok">>})),
                    {noreply, S};

                <<"ets_incr">> ->
                    P = maps:get(<<"payload">>, D),
                    Key = maps:get(<<"key">>, P),
                    Amount = maps:get(<<"amount">>, P, 1),
                    NewVal = try ets:update_counter(omnicorn_cache, Key, {2, Amount}, {Key, 0, 0}) catch _:_ -> nil end,
                    gen_tcp:send(S#state.data_socket, term_to_binary(#{<<"id">> => maps:get(<<"id">>, D), <<"type">> => <<"ets_reply">>, <<"data">> => NewVal})),
                    {noreply, S};

                <<"activity_enqueue">> ->
                    omn_task_broker:enqueue(maps:get(<<"payload">>, D)),
                    gen_tcp:send(S#state.data_socket, term_to_binary(#{<<"id">> => maps:get(<<"id">>, D), <<"type">> => <<"ets_reply">>, <<"data">> => <<"queued">>})),
                    {noreply, S};

                <<"activity_ack">> ->
                    omn_task_broker:ack(maps:get(<<"activity_id">>, D)),
                    {noreply, S};

                <<"activity_fail">> ->
                    omn_task_broker:fail(maps:get(<<"activity_id">>, D), maps:get(<<"error">>, D)),
                    {noreply, S};

                <<"workflow_start">> ->
                    P = maps:get(<<"payload">>, D),
                    omn_actor_manager:start_workflow(maps:get(<<"workflow_id">>, P), maps:get(<<"name">>, P), maps:get(<<"data">>, P)),
                    gen_tcp:send(S#state.data_socket, term_to_binary(#{<<"id">> => maps:get(<<"id">>, D), <<"type">> => <<"ets_reply">>, <<"data">> => <<"started">>})),
                    {noreply, S};

                <<"workflow_checkpoint">> ->
                    omn_actor_manager:checkpoint_ack(maps:get(<<"workflow_id">>, D), maps:get(<<"next_step">>, D), maps:get(<<"sleep_ms">>, D), maps:get(<<"data">>, D)),
                    {noreply, S};

                _ ->
                    case maps:get(<<"status">>, D, undefined) of
                        <<"ready">> ->
                            omn_router:checkin_worker(self()),
                            {noreply, S};
                        _ ->
                            case maps:take(maps:get(<<"id">>, D), S#state.reqs) of
                                {From, NR} ->
                                    gen_server:reply(From, maps:get(<<"data">>, D)),
                                    omn_router:checkin_worker(self()),
                                    {noreply, S#state{reqs=NR}};
                                error ->
                                    {noreply, S}
                            end
                    end
            end
    catch _:_ -> {noreply, S} end;

handle_info({Port, {data, L}}, S = #state{log_port=Port}) ->
    io:format("[PY] ~s", [L]),
    {noreply, S};
handle_info({Port, {exit_status, _}}, S = #state{log_port=Port}) ->
    {stop, died, S};
handle_info(_, S) ->
    {noreply, S}.

terminate(_Reason, State) ->
    catch gen_tcp:close(State#state.data_socket),
    catch gen_tcp:close(State#state.listener),
    catch file:delete(State#state.path),
    catch port_close(State#state.log_port),
    ok.

code_change(_OldVsn, State, _Extra) ->
    {ok, State}.

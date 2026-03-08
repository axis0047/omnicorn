-module(omn_ws_handler).
-behaviour(cowboy_websocket).
-export([init/2, websocket_init/1, websocket_handle/2, websocket_info/2, websocket_terminate/3]).

-record(state, {
    req,
    pid,
    worker_id,
    req_id,
    connection_state = #{}
}).

%% 1. INITIAL HANDSHAKE
init(Req, _Opts) ->
    ReqId = erlang:phash2(erlang:make_ref()),

    PythonPayload = #{
        <<"scope_type">> => <<"websocket">>,
        <<"id">>         => ReqId,
        <<"path">>       => cowboy_req:path(Req),
        <<"query">>      => cowboy_req:qs(Req),
        <<"headers">>    => cowboy_req:headers(Req),
        <<"scheme">>     => cowboy_req:scheme(Req),
        <<"port">>       => cowboy_req:port(Req)
    },

    case omn_router:checkout_worker() of
        {ok, WorkerPid} ->
            case omn_worker:call_python(WorkerPid, <<"websocket_handshake">>, PythonPayload) of
                {ok, Resp} ->
                    case maps:get(<<"websocket_handshake">>, Resp, <<"error">>) of
                        <<"accept">> ->
                            State = #state{
                                req = Req,
                                pid = WorkerPid,
                                worker_id = WorkerPid,
                                req_id = ReqId
                            },
                            {cowboy_websocket, Req, State};

                        <<"close">> ->
                            Code = maps:get(<<"code">>, Resp, 403),
                            {ok, cowboy_req:reply(Code, Req), undefined};

                        _ ->
                            {ok, cowboy_req:reply(500, Req), undefined}
                    end;
                {error, _} ->
                     {ok, cowboy_req:reply(502, Req), undefined}
            end;
        {error, empty} ->
            {ok, cowboy_req:reply(503, Req), undefined}
    end.

websocket_init(State) ->
    io:format("[WS] Connection ~p established~n", [State#state.req_id]),
    {ok, State}.

%% 2. HANDLE INCOMING FRAMES
websocket_handle({text, Data}, State) ->
    forward(<<"text">>, Data, State);
websocket_handle({binary, Data}, State) ->
    forward(<<"binary">>, Data, State);
websocket_handle(_Frame, State) ->
    {ok, State}.

websocket_info(_Info, State) ->
    {ok, State}.

websocket_terminate(Reason, _Req, #state{pid=Pid, req_id=ReqId, connection_state=CS}) ->
    Msg = #{
        <<"id">> => ReqId,
        <<"type">> => <<"websocket_disconnect">>,
        <<"payload">> => #{<<"code">> => 1000, <<"connection_state">> => CS}
    },
    omn_worker:call_python(Pid, <<"websocket_disconnect">>, Msg),
    io:format("[WS] Closed ~p: ~p~n", [ReqId, Reason]),
    ok;
websocket_terminate(_Reason, _Req, _State) -> ok.

forward(Type, Data, State = #state{pid=Pid, req_id=ReqId, connection_state=CS}) ->
    Msg = #{
        <<"id">> => ReqId,
        <<"type">> => <<"websocket_message">>,
        <<"payload">> => #{
            <<"message_type">> => Type,
            <<"content">> => Data,
            <<"connection_state">> => CS
        }
    },
    case omn_worker:call_python(Pid, <<"websocket_message">>, Msg) of
        {ok, Resp} ->
            NewCS = maps:get(<<"connection_state">>, Resp, CS),
            Actions = parse_actions(maps:get(<<"websocket_message_response">>, Resp, [])),
            {Actions, State#state{connection_state = NewCS}};
        _ ->
            {stop, worker_error, State}
    end.

parse_actions(List) when is_list(List) ->
    lists:foldl(fun(M, Acc) ->
        case maps:get(<<"type">>, M, <<>>) of
            <<"send_text">> -> Acc ++ [{text, maps:get(<<"content">>, M)}];
            <<"send_binary">> -> Acc ++ [{binary, maps:get(<<"content">>, M)}];
            <<"close">> -> Acc ++ [close];
            _ -> Acc
        end
    end, [], List);
parse_actions(_) -> [].

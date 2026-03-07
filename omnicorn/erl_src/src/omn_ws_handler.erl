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

    %% Prepare Handshake Payload for Python
    PythonPayload = #{
        <<"scope_type">> => <<"websocket">>,
        <<"id">>         => ReqId,
        <<"path">>       => cowboy_req:path(Req),
        <<"query">>      => cowboy_req:qs(Req),
        <<"headers">>    => cowboy_req:headers(Req),
        <<"scheme">>     => cowboy_req:scheme(Req),
        <<"port">>       => cowboy_req:port(Req)
    },

    %% Ask a Python worker if we can accept this connection
    case omn_router:checkout_worker() of
        {ok, WorkerPid} ->
            case omn_worker:call_python(WorkerPid, <<"websocket_handshake">>, PythonPayload) of
                {ok, Resp} ->
                    case maps:get(<<"websocket_handshake">>, Resp, <<"error">>) of
                        <<"accept">> ->
                            %% Success! Upgrade to WebSocket
                            State = #state{
                                req = Req,
                                pid = WorkerPid,
                                worker_id = WorkerPid,
                                req_id = ReqId
                            },
                            %% Handle Subprotocol if present
                            case maps:get(<<"subprotocol">>, Resp, undefined) of
                                undefined ->
                                    {cowboy_websocket, Req, State};
                                SubProto ->
                                    Req2 = cowboy_req:set_resp_header(<<"sec-websocket-protocol">>, SubProto, Req),
                                    {cowboy_websocket, Req2, State}
                            end;

                        <<"close">> ->
                            %% Python rejected it (e.g. 403 Forbidden)
                            Code = maps:get(<<"code">>, Resp, 403),
                            Req2 = cowboy_req:reply(Code, Req),
                            {ok, Req2, undefined};

                        _ ->
                            Req2 = cowboy_req:reply(500, #{}, <<"Handshake Error">>, Req),
                            {ok, Req2, undefined}
                    end;
                {error, _Reason} ->
                     Req2 = cowboy_req:reply(502, #{}, <<"Worker Timeout/Error">>, Req),
                     {ok, Req2, undefined}
            end;
        {error, empty} ->
            Req2 = cowboy_req:reply(503, #{}, <<"No Workers Available">>, Req),
            {ok, Req2, undefined}
    end.

websocket_init(State) ->
    io:format("[WS] Connection ~p established~n", [State#state.req_id]),
    {ok, State}.

%% 2. HANDLE INCOMING FRAMES (From Client)
websocket_handle({text, Data}, State) ->
    forward_to_python(<<"text">>, Data, State);
websocket_handle({binary, Data}, State) ->
    forward_to_python(<<"binary">>, Data, State);
websocket_handle(_Frame, State) ->
    {ok, State}.

%% 3. HANDLE MESSAGES FROM PYTHON (Via omn_worker)
%% Currently, omn_worker calls us synchronously, but if we add async support later:
websocket_info(_Info, State) ->
    {ok, State}.

websocket_terminate(Reason, _Req, #state{pid=Pid, req_id=ReqId, connection_state=CS}) ->
    %% Tell Python to clean up
    Msg = #{
        <<"id">> => ReqId,
        <<"type">> => <<"websocket_disconnect">>,
        <<"payload">> => #{
            <<"code">> => 1000,
            <<"connection_state">> => CS
        }
    },
    omn_worker:call_python(Pid, <<"websocket_disconnect">>, Msg),
    io:format("[WS] Connection ~p closed: ~p~n", [ReqId, Reason]),
    ok;
websocket_terminate(_Reason, _Req, _State) ->
    ok.

%% INTERNAL HELPERS
forward_to_python(Type, Data, State = #state{pid=Pid, req_id=ReqId, connection_state=CS}) ->
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

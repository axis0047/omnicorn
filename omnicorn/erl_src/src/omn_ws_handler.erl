-module(omn_ws_handler).
-behaviour(cowboy_websocket).
-export([init/2, websocket_init/1, websocket_handle/2, websocket_info/2, websocket_terminate/3]).
-record(state, {pid, req_id}).

init(Req, _Opts) ->
    ReqId = erlang:phash2(erlang:make_ref()),
    Payload = #{<<"id">> => ReqId, <<"path">> => cowboy_req:path(Req), <<"headers">> => cowboy_req:headers(Req)},
    case omn_router:checkout_worker() of
        {ok, Pid} ->
            case omn_worker:call_python(Pid, <<"websocket_handshake">>, Payload) of
                {ok, R} ->
                    case maps:get(<<"websocket_handshake">>, R) of
                        <<"accept">> -> {cowboy_websocket, Req, #state{pid=Pid, req_id=ReqId}};
                        _ -> {ok, cowboy_req:reply(403, Req), undefined}
                    end;
                _ -> {ok, cowboy_req:reply(502, Req), undefined}
            end;
        _ -> {ok, cowboy_req:reply(503, Req), undefined}
    end.

websocket_init(State) -> {ok, State}.

websocket_handle({text, D}, S) -> forward(<<"text">>, D, S);
websocket_handle({binary, D}, S) -> forward(<<"binary">>, D, S).

websocket_info(_, S) -> {ok, S}.

websocket_terminate(_, _, S) ->
    omn_worker:call_python(S#state.pid, <<"websocket_disconnect">>, #{<<"id">> => S#state.req_id}),
    ok.

forward(Type, Data, S) ->
    {ok, R} = omn_worker:call_python(S#state.pid, <<"websocket_message">>, #{
        <<"id">> => S#state.req_id,
        <<"message_type">> => Type,
        <<"content">> => Data
    }),

    %% FIX: Replaced illegal 'if' guard with a valid 'case' statement inside the list comprehension
    Actions =[
        case maps:get(<<"type">>, M) of
            <<"send_text">> -> {text, maps:get(<<"content">>, M)};
            _ -> {binary, maps:get(<<"content">>, M)}
        end
        || M <- maps:get(<<"websocket_message_response">>, R, [])
    ],
    {Actions, S}.

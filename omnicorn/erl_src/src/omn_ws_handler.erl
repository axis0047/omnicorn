-module(omn_ws_handler).
-behaviour(cowboy_websocket).
-export([init/2, websocket_init/1, websocket_handle/2, websocket_info/2, websocket_terminate/3]).
-record(state, {pid, req_id}).

init(Req, _Opts) ->
    ReqId = erlang:phash2(erlang:make_ref()),

    %% 🔥 THE FIX: Register the WS connection BEFORE talking to Python.
    %% This guarantees the ReqId exists in ETS before Python can possibly reply!
    omn_router:register_ws(ReqId, self()),

    Payload = #{
        <<"id">> => ReqId,
        <<"path">> => cowboy_req:path(Req),
        <<"query">> => cowboy_req:qs(Req),
        <<"port">> => cowboy_req:port(Req),
        <<"scheme">> => cowboy_req:scheme(Req),
        <<"headers">> => cowboy_req:headers(Req)
    },

    case omn_router:checkout_worker() of
        {ok, Pid} ->
            case omn_worker:call_python(Pid, <<"websocket_handshake">>, Payload) of
                {ok, R} ->
                    case maps:get(<<"websocket_handshake">>, R) of
                        <<"accept">> ->
                            {cowboy_websocket, Req, #state{pid=Pid, req_id=ReqId}};
                        _ ->
                            %% If rejected, clean up the registry
                            omn_router:unregister_ws(ReqId),
                            {ok, cowboy_req:reply(403, Req), undefined}
                    end;
                _ ->
                    omn_router:unregister_ws(ReqId),
                    {ok, cowboy_req:reply(502, Req), undefined}
            end;
        _ ->
            omn_router:unregister_ws(ReqId),
            {ok, cowboy_req:reply(503, Req), undefined}
    end.

websocket_init(State) -> {ok, State}.

websocket_handle({text, D}, S) -> forward(<<"text">>, D, S);
websocket_handle({binary, D}, S) -> forward(<<"binary">>, D, S);
websocket_handle(_Frame, S) -> {ok, S}.

websocket_info({push, ActionsMapList}, S) ->
    Actions =[
        case maps:get(<<"type">>, M) of
            <<"send_text">> -> {text, maps:get(<<"content">>, M)};
            <<"send_binary">> -> {binary, maps:get(<<"content">>, M)};
            <<"close">> -> close
        end
        || M <- ActionsMapList
    ],
    {Actions, S};
websocket_info(_, S) -> {ok, S}.

websocket_terminate(_, _, S) ->
    omn_router:unregister_ws(S#state.req_id),
    omn_worker:send_async(S#state.pid, #{
        <<"type">> => <<"websocket_disconnect">>,
        <<"payload">> => #{<<"id">> => S#state.req_id}
    }),
    ok.

forward(Type, Data, S) ->
    omn_worker:send_async(S#state.pid, #{
        <<"type">> => <<"websocket_message">>,
        <<"payload">> => #{
            <<"id">> => S#state.req_id,
            <<"message_type">> => Type,
            <<"content">> => Data
        }
    }),
    {[], S}.

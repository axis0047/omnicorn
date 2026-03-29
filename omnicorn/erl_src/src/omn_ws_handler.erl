-module(omn_ws_handler).
-behaviour(cowboy_websocket).
-export([init/2, websocket_init/1, websocket_handle/2, websocket_info/2, websocket_terminate/3]).
-record(state, {pid, req_id}).

init(Req, _Opts) ->
    ReqId = erlang:phash2(erlang:make_ref()),

    %% Register immediately to prevent routing misses
    ets:insert(omn_ws_registry, {ReqId, self()}),

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
                            ets:delete(omn_ws_registry, ReqId),
                            {ok, cowboy_req:reply(403, Req), undefined}
                    end;
                _ ->
                    ets:delete(omn_ws_registry, ReqId),
                    {ok, cowboy_req:reply(502, Req), undefined}
            end;
        _ ->
            ets:delete(omn_ws_registry, ReqId),
            {ok, cowboy_req:reply(503, Req), undefined}
    end.

websocket_init(State) ->
    io:format("[Erlang WS] Cowboy Loop Started. Sweeping mailbox for early frames...~n"),
    %% 🔥 THE FIX: Manually sweep the mailbox for messages that arrived during the handshake
    EarlyFrames = flush_pushes([]),
    case EarlyFrames of[] ->
            {ok, State};
        _ ->
            io:format("[Erlang WS] Flushed ~p early frames to client!~n",[length(EarlyFrames)]),
            {reply, EarlyFrames, State}
    end.

%% Recursive Mailbox Sweeper
flush_pushes(Acc) ->
    receive
        {push, ActionsMapList} ->
            Frames = lists:filtermap(fun format_frame/1, ActionsMapList),
            flush_pushes(Acc ++ Frames)
    after 0 ->
        Acc
    end.

websocket_handle({text, D}, S) -> forward(<<"text">>, D, S);
websocket_handle({binary, D}, S) -> forward(<<"binary">>, D, S);
websocket_handle(_Frame, S) -> {ok, S}.

websocket_info({push, ActionsMapList}, S) ->
    Frames = lists:filtermap(fun format_frame/1, ActionsMapList),
    case Frames of[] -> {ok, S};
        [SingleFrame] -> {reply, SingleFrame, S};
        MultipleFrames -> {reply, MultipleFrames, S}
    end;
websocket_info(_, S) ->
    {ok, S}.

websocket_terminate(_, _, S) ->
    ets:delete(omn_ws_registry, S#state.req_id),
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
    {ok, S}.

%% Helper to safely extract Python dicts into Cowboy frames
format_frame(M) ->
    case maps:get(<<"type">>, M, undefined) of
        <<"send_text">> -> {true, {text, maps:get(<<"content">>, M, <<"">>)}};
        <<"send_binary">> -> {true, {binary, maps:get(<<"content">>, M, <<>>)}};
        <<"close">> -> {true, close};
        _ -> false
    end.

-module(omn_http).
-export([init/2]).

-define(RESET,   "\e[0m").
-define(RED,     "\e[31m").
-define(GREEN,   "\e[32m").
-define(YELLOW,  "\e[33m").
-define(CYAN,    "\e[36m").

init(Req, State) ->
    %% Check for WebSocket Upgrade Request
    %% FIX 1: cowboy_req:is_upgrade/2 does not exist in Cowboy.
    %% The correct approach is to inspect the "upgrade" header directly.
    case cowboy_req:header(<<"upgrade">>, Req) of
        <<"websocket">> -> handle_websocket_upgrade(Req, State);
        _               -> handle_http_request(Req, State)
    end.

handle_http_request(Req, State) ->
    StartTime = erlang:monotonic_time(microsecond),

    {ok, Body, Req2} = read_body(Req, <<>>),

    PythonPayload = #{
        <<"scope_type">> => <<"http">>,
        <<"method">>     => cowboy_req:method(Req2),
        <<"path">>       => cowboy_req:path(Req2),
        <<"query">>      => cowboy_req:qs(Req2),
        <<"headers">>    => cowboy_req:headers(Req2),
        <<"scheme">>     => cowboy_req:scheme(Req2),
        <<"body">>       => Body,
        <<"port">>       => cowboy_req:port(Req2)
    },

    Response = case omn_router:checkout_worker() of
        {ok, WorkerPid} ->
            case omn_worker:call_python(WorkerPid, <<"http">>, PythonPayload) of
                {ok, WorkerResponse} ->
                    WorkerResponse;
                {error, timeout} ->
                    exit(WorkerPid, kill),
                    gateway_timeout();
                {error, Reason} ->
                    io:format("[HTTP] Worker ~p crashed: ~p~n", [WorkerPid, Reason]),
                    internal_server_error()
            end;
        {error, empty} ->
            service_unavailable()
    end,

    Status = case maps:get(<<"status">>, Response, 500) of
        S when is_binary(S) -> binary_to_integer(S);
        S -> S
    end,

    Headers  = maps:get(<<"headers">>, Response, []),
    RespBody = maps:get(<<"body">>,    Response, <<>>),

    %% FIX 2: Headers from Python are likely a map (binary keys/values).
    %% cowboy_req:reply/4 expects a map or list of {binary(), iodata()} pairs.
    %% atom_to_binary on a binary key would crash; use the keys as-is.
    CowboyHeaders = case Headers of
        M when is_map(M) -> M;
        L when is_list(L) -> maps:from_list(L)
    end,

    Req3 = cowboy_req:reply(Status, CowboyHeaders, RespBody, Req2),

    EndTime   = erlang:monotonic_time(microsecond),
    LatencyUs = EndTime - StartTime,
    log_request(Req3, Status, LatencyUs),

    {ok, Req3, State}.

handle_websocket_upgrade(Req, State) ->
    ReqId = make_ref(),

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
            case omn_worker:call_python(
                WorkerPid,
                <<"websocket_handshake">>,
                PythonPayload
            ) of

                {ok, PythonHandshakeResponse} when is_map(PythonHandshakeResponse) ->
                    case maps:get(
                        <<"websocket_handshake">>,
                        PythonHandshakeResponse,
                        <<"error">>
                    ) of

                        <<"accept">> ->
                            Subprotocol =
                                maps:get(
                                    <<"subprotocol">>,
                                    PythonHandshakeResponse,
                                    undefined
                                ),

                            io:format(
                                "[WS] Handshake accepted by worker ~p for connection ~p~n",
                                [WorkerPid, ReqId]
                            ),

                            %% FIX 3: #omn_ws_handler.state{} is not valid record syntax.
                            %% Record syntax is #record_name{field = value}.
                            %% Using a plain map here; replace with your actual record
                            %% definition if you have one (e.g. -record(omn_ws_state, {...})).
                            WSState = #{
                                req              => Req,
                                pid              => WorkerPid,
                                worker_id        => WorkerPid,
                                req_id           => ReqId,
                                connection_state => []
                            },

                            case Subprotocol of
                                undefined ->
                                    {cowboy_websocket, Req, WSState};
                                _ ->
                                    {cowboy_websocket, Req, WSState,
                                        #{subprotocol => Subprotocol}}
                            end;

                        <<"close">> ->
                            Code =
                                maps:get(
                                    <<"code">>,
                                    PythonHandshakeResponse,
                                    1000
                                ),

                            io:format(
                                "[WS] Handshake rejected by worker ~p for connection ~p (Code: ~p)~n",
                                [WorkerPid, ReqId, Code]
                            ),

                            Req2 =
                                cowboy_req:reply(
                                    400,
                                    #{},
                                    <<"WebSocket handshake rejected">>,
                                    Req
                                ),

                            {ok, Req2, State};

                        _ ->
                            io:format(
                                "[WS] Invalid handshake response from worker ~p for connection ~p: ~p~n",
                                [WorkerPid, ReqId, PythonHandshakeResponse]
                            ),

                            Req2 =
                                cowboy_req:reply(
                                    500,
                                    #{},
                                    <<"WebSocket handshake internal error">>,
                                    Req
                                ),

                            {ok, Req2, State}
                    end;

                {ok, InvalidResponse} ->
                    io:format(
                        "[WS] Non-map response from worker ~p for connection ~p: ~p~n",
                        [WorkerPid, ReqId, InvalidResponse]
                    ),

                    Req2 =
                        cowboy_req:reply(
                            500,
                            #{},
                            <<"Invalid handshake response">>,
                            Req
                        ),

                    {ok, Req2, State};

                {error, timeout} ->
                    exit(WorkerPid, timeout),

                    io:format(
                        "[WS] Handshake worker ~p timed out for connection ~p~n",
                        [WorkerPid, ReqId]
                    ),

                    Req2 =
                        cowboy_req:reply(
                            504,
                            #{},
                            <<"WebSocket handshake timeout">>,
                            Req
                        ),

                    {ok, Req2, State};

                {error, Reason} ->
                    io:format(
                        "[WS] Handshake worker ~p crashed for connection ~p: ~p~n",
                        [WorkerPid, ReqId, Reason]
                    ),

                    Req2 =
                        cowboy_req:reply(
                            500,
                            #{},
                            <<"WebSocket handshake worker crashed">>,
                            Req
                        ),

                    {ok, Req2, State}
            end;

        {error, empty} ->
            io:format(
                "[WS] No workers available for handshake for connection ~p~n",
                [ReqId]
            ),

            Req2 =
                cowboy_req:reply(
                    503,
                    #{},
                    <<"Service Unavailable - No workers">>,
                    Req
                ),

            {ok, Req2, State}
    end.

read_body(Req, Acc) ->
    case cowboy_req:read_body(Req) of
        {ok, Data, Req2}   -> {ok, <<Acc/binary, Data/binary>>, Req2};
        {more, Data, Req2} -> read_body(Req2, <<Acc/binary, Data/binary>>)
    end.

gateway_timeout() ->
    #{<<"status">> => 504, <<"body">> => <<"504 Gateway Timeout">>}.

service_unavailable() ->
    #{<<"status">> => 503, <<"body">> => <<"503 Service Unavailable">>}.

internal_server_error() ->
    #{<<"status">> => 500, <<"body">> => <<"500 Internal Server Error">>}.

log_request(Req, Status, LatencyUs) ->
    Method = cowboy_req:method(Req),
    Path   = cowboy_req:path(Req),

    {{Y,M,D},{H,Min,S}} = calendar:local_time(),
    TimeStr = io_lib:format("~4..0w-~2..0w-~2..0w ~2..0w:~2..0w:~2..0w",
                            [Y,M,D,H,Min,S]),

    LatencyMs = LatencyUs / 1000.0,

    Color = if
        Status >= 500 -> ?RED;
        Status >= 400 -> ?YELLOW;
        Status >= 300 -> ?CYAN;
        true          -> ?GREEN
    end,

    io:format("[~s] \"~s ~s\" ~s~p~s - ~.2fms~n",
              [TimeStr, Method, Path, Color, Status, ?RESET, LatencyMs]).

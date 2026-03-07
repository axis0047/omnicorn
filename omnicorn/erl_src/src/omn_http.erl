-module(omn_http).
-export([init/2]).

%% ANSI Colors for Terminal Output
-define(RESET,   "\e[0m").
-define(RED,     "\e[31m").
-define(GREEN,   "\e[32m").
-define(YELLOW,  "\e[33m").
-define(CYAN,    "\e[36m").

init(Req, State) ->
    %% 1. Start Timer for Latency Tracking
    StartTime = erlang:monotonic_time(microsecond),

    %% 2. Read Body
    {ok, Body, Req2} = read_body(Req, <<>>),

    %% 3. Prepare Payload
    Payload = #{
        <<"method">> => cowboy_req:method(Req2),
        <<"path">> => cowboy_req:path(Req2),
        <<"query">> => cowboy_req:qs(Req2),
        <<"headers">> => cowboy_req:headers(Req2),
        <<"scheme">> => cowboy_req:scheme(Req2),
        <<"body">> => Body,
        <<"port">> => cowboy_req:port(Req2)
    },

    %% 4. Get Worker & Execute
    Response = case omn_router:checkout_worker() of
        {ok, WorkerPid} ->
            case omn_worker:call_python(WorkerPid, <<"http">>, Payload) of
                {error, timeout} ->
                    exit(WorkerPid, kill),
                    gateway_timeout();
                WorkerResponse ->
                    WorkerResponse
            end;
        {error, empty} ->
            service_unavailable()
    end,

    %% 5. Extract Status and Send Reply
    %% Ensure Status is an integer
    Status = case maps:get(<<"status">>, Response, 500) of
        S when is_binary(S) -> binary_to_integer(S);
        S -> S
    end,

    Headers = maps:get(<<"headers">>, Response, #{}),
    RespBody = maps:get(<<"body">>, Response, <<>>),

    Req3 = cowboy_req:reply(Status, Headers, RespBody, Req2),

    %% 6. Log to Terminal
    EndTime = erlang:monotonic_time(microsecond),
    LatencyUs = EndTime - StartTime,
    log_request(Req3, Status, LatencyUs),

    {ok, Req3, State}.

%% ===================================================================
%% Internal Helpers
%% ===================================================================

%% Recursively read body chunks
read_body(Req, Acc) ->
    case cowboy_req:read_body(Req) of
        {ok, Data, Req2} -> {ok, <<Acc/binary, Data/binary>>, Req2};
        {more, Data, Req2} -> read_body(Req2, <<Acc/binary, Data/binary>>)
    end.

%% Standard Error Responses
gateway_timeout() ->
    #{<<"status">> => 504, <<"body">> => <<"504 Gateway Timeout">>}.

service_unavailable() ->
    #{<<"status">> => 503, <<"body">> => <<"503 Service Unavailable">>}.

%% ===================================================================
%% Logging Logic
%% ===================================================================

log_request(Req, Status, LatencyUs) ->
    Method = cowboy_req:method(Req),
    Path = cowboy_req:path(Req),

    %% Format Timestamp: [YYYY-MM-DD HH:MM:SS]
    {{Y,M,D},{H,Min,S}} = calendar:local_time(),
    TimeStr = io_lib:format("~4..0w-~2..0w-~2..0w ~2..0w:~2..0w:~2..0w",
                            [Y,M,D,H,Min,S]),

    %% Format Latency (ms)
    LatencyMs = LatencyUs / 1000.0,

    %% Determine Color based on Status Code
    Color = if
        Status >= 500 -> ?RED;
        Status >= 400 -> ?YELLOW;
        Status >= 300 -> ?CYAN;
        true -> ?GREEN
    end,

    %% Print to Stdout: [Time] "METHOD /path" STATUS - Latency
    io:format("[~s] \"~s ~s\" ~s~p~s - ~.2fms~n",
              [TimeStr, Method, Path, Color, Status, ?RESET, LatencyMs]).

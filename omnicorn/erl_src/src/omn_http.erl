-module(omn_http).
-export([init/2]).

-define(RESET,   "\e[0m").
-define(RED,     "\e[31m").
-define(GREEN,   "\e[32m").
-define(YELLOW,  "\e[33m").
-define(CYAN,    "\e[36m").

init(Req, State) ->
    StartTime = erlang:monotonic_time(microsecond),

    {ok, Body, Req2} = read_body(Req, <<>>),

    Payload = #{
        <<"scope_type">> => <<"http">>,
        <<"method">> => cowboy_req:method(Req2),
        <<"path">> => cowboy_req:path(Req2),
        <<"query">> => cowboy_req:qs(Req2),
        <<"headers">> => cowboy_req:headers(Req2),
        <<"scheme">> => cowboy_req:scheme(Req2),
        <<"body">> => Body,
        <<"port">> => cowboy_req:port(Req2)
    },

    Response = case omn_router:checkout_worker() of
        {ok, WorkerPid} ->
            case omn_worker:call_python(WorkerPid, <<"http">>, Payload) of
                {ok, Res} -> Res;
                {error, timeout} ->
                    exit(WorkerPid, kill),
                    #{<<"status">> => 504, <<"body">> => <<"Gateway Timeout">>};
                {error, _} ->
                    #{<<"status">> => 502, <<"body">> => <<"Bad Gateway">>}
            end;
        {error, empty} ->
            #{<<"status">> => 503, <<"body">> => <<"Service Unavailable">>}
    end,

    Status = case maps:get(<<"status">>, Response, 500) of
        S when is_binary(S) -> binary_to_integer(S);
        S -> S
    end,

    Headers = maps:get(<<"headers">>, Response, #{}),
    RespBody = maps:get(<<"body">>, Response, <<>>),

    %% Convert Atom keys to Binary, and strictly LOWERCASE them!
    %% Cowboy 2.0+ strictly enforces HTTP/2 rules which dictate all lowercase keys.
    CowboyHeaders = maps:fold(fun(K, V, Acc) ->
        BinK = if is_atom(K) -> atom_to_binary(K, utf8); true -> K end,
        LowerK = string:lowercase(BinK),

        %% Also ensure values are binaries (Flask might return ints)
        BinV = if
            is_integer(V) -> integer_to_binary(V);
            is_list(V) -> iolist_to_binary(V);
            is_atom(V) -> atom_to_binary(V, utf8);
            true -> V
        end,
        Acc#{LowerK => BinV}
    end, #{}, Headers),

    Req3 = cowboy_req:reply(Status, CowboyHeaders, RespBody, Req2),

    EndTime = erlang:monotonic_time(microsecond),
    log_request(Req3, Status, EndTime - StartTime),

    {ok, Req3, State}.

read_body(Req, Acc) ->
    case cowboy_req:read_body(Req) of
        {ok, Data, Req2} -> {ok, <<Acc/binary, Data/binary>>, Req2};
        {more, Data, Req2} -> read_body(Req2, <<Acc/binary, Data/binary>>)
    end.

log_request(Req, Status, LatencyUs) ->
    Method = cowboy_req:method(Req),
    Path = cowboy_req:path(Req),
    LatencyMs = LatencyUs / 1000.0,
    Color = if Status >= 500 -> ?RED; Status >= 400 -> ?YELLOW; true -> ?GREEN end,
    io:format("[HTTP] \"~s ~s\" ~s~p~s - ~.2fms~n",[Method, Path, Color, Status, ?RESET, LatencyMs]).

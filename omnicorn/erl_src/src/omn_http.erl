-module(omn_http).
-export([init/2]).

init(Req, State) ->
    %% 1. Read the Full Request Body
    %% Important: Python WSGI expects the full body immediately in this architecture.
    {ok, Body, Req2} = read_body(Req, <<>>),

    %% 2. Prepare Payload
    Payload = #{
        <<"method">> => cowboy_req:method(Req2),
        <<"path">> => cowboy_req:path(Req2),
        <<"query">> => cowboy_req:qs(Req2),
        <<"headers">> => cowboy_req:headers(Req2),
        <<"scheme">> => cowboy_req:scheme(Req2),
        <<"body">> => Body,
        <<"port">> => cowboy_req:port(Req2)
    },

    %% 3. Get a Worker
    Response = case omn_router:checkout_worker() of
        {ok, WorkerPid} ->
            %% 4. Execute with Fault Tolerance
            case omn_worker:call_python(WorkerPid, <<"http">>, Payload) of
                {error, timeout} ->
                    %% KILL STRATEGY:
                    %% If it timed out, the Python process is likely stuck.
                    %% We hard-kill it so the supervisor spawns a fresh one.
                    exit(WorkerPid, kill),
                    gateway_timeout();

                WorkerResponse ->
                    %% Normal Response
                    WorkerResponse
            end;
        {error, empty} ->
            %% BACKPRESSURE: No workers available
            service_unavailable()
    end,

    %% 5. Send Reply
    Status = maps:get(<<"status">>, Response, 500),
    Headers = maps:get(<<"headers">>, Response, #{}),
    RespBody = maps:get(<<"body">>, Response, <<>>),

    Req3 = cowboy_req:reply(Status, Headers, RespBody, Req2),
    {ok, Req3, State}.

%% Recursively read body chunks
read_body(Req, Acc) ->
    case cowboy_req:read_body(Req) of
        {ok, Data, Req2} -> {ok, <<Acc/binary, Data/binary>>, Req2};
        {more, Data, Req2} -> read_body(Req2, <<Acc/binary, Data/binary>>)
    end.

gateway_timeout() ->
    #{
        <<"status">> => 504,
        <<"headers">> => #{<<"content-type">> => <<"text/plain">>},
        <<"body">> => <<"504 Gateway Timeout - Worker unresponsive">>
    }.

service_unavailable() ->
    #{
        <<"status">> => 503,
        <<"headers">> => #{<<"content-type">> => <<"text/plain">>},
        <<"body">> => <<"503 Service Unavailable - All workers busy">>
    }.

-module(omn_http).
-export([init/2]).
init(Req, State) ->
    {ok, Body, Req2} = cowboy_req:read_body(Req),
    Payload = #{<<"method">> => cowboy_req:method(Req2), <<"path">> => cowboy_req:path(Req2), <<"headers">> => cowboy_req:headers(Req2), <<"body">> => Body},

    Response = case omn_router:checkout_worker() of
        {ok, WorkerPid} -> case omn_worker:call_python(WorkerPid, <<"http">>, Payload) of {ok, Res} -> Res; _ -> #{<<"status">> => 502} end;
        _ -> #{<<"status">> => 503}
    end,

    Headers = maps:fold(fun(K, V, Acc) -> Acc#{string:lowercase(if is_atom(K) -> atom_to_binary(K); true -> K end) => V} end, #{}, maps:get(<<"headers">>, Response, #{})),
    Req3 = cowboy_req:reply(maps:get(<<"status">>, Response, 500), Headers, maps:get(<<"body">>, Response, <<>>), Req2),
    {ok, Req3, State}.

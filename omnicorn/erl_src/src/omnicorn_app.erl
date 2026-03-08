-module(omnicorn_app).
-behaviour(application).
-export([start/2, stop/1]).

start(_StartType, _StartArgs) ->
    PortStr = os:getenv("OMNICORN_PORT", "8080"),
    WorkersStr = os:getenv("OMNICORN_WORKERS", "4"),
    AppPath = os:getenv("OMNICORN_APP", "demo:app"),

    Port = list_to_integer(PortStr),
    WorkerCount = list_to_integer(WorkersStr),

    io:format("[Omnicorn] Starting Control Plane on Port ~p...~n", [Port]),

    %% 🔥 SUPERPOWER: Create a global, highly concurrent in-memory database.
    %% read_concurrency and write_concurrency allow completely lock-free access across all workers!
    ets:new(omnicorn_cache,[named_table, public, set, {read_concurrency, true}, {write_concurrency, true}]),

    Dispatch = cowboy_router:compile([
        {'_',[
            {<<"/ws/[...]">>, omn_ws_handler, []},
            {'_', omn_http,[]}
        ]}
    ]),

    {ok, _} = cowboy:start_clear(http_listener,
        [{port, Port}],
        #{env => #{dispatch => Dispatch}}
    ),

    omnicorn_sup:start_link(WorkerCount, AppPath).

stop(_State) -> ok.

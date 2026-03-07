-module(omnicorn_app).
-behaviour(application).
-export([start/2, stop/1]).

start(_StartType, _StartArgs) ->
    PortStr = os:getenv("OMNICORN_PORT", "8080"),
    WorkersStr = os:getenv("OMNICORN_WORKERS", "4"),
    AppPath = os:getenv("OMNICORN_APP", "demo:app"),

    Port = list_to_integer(PortStr),
    WorkerCount = list_to_integer(WorkersStr),

    io:format("[Omnicorn] Starting Control Plane on Port ~p with ~p workers wrapping ~s~n",
              [Port, WorkerCount, AppPath]),

    %% Define Routes
    Dispatch = cowboy_router:compile([
        {'_', [
            %% 1. WebSocket Route: Explicitly match /ws (and subpaths)
            {<<"/ws/[...]">>, omn_ws_handler, []},

            %% 2. Catch-all HTTP Route
            {'_', omn_http, []}
        ]}
    ]),

    {ok, _} = cowboy:start_clear(http_listener,
        [{port, Port}],
        #{env => #{dispatch => Dispatch}}
    ),

    omnicorn_sup:start_link(WorkerCount, AppPath).

stop(_State) ->
    ok.

-module(omnicorn_app).
-behaviour(application).
-export([start/2, stop/1]).

start(_StartType, _StartArgs) ->
    %% 1. Configuration
    PortStr = os:getenv("OMNICORN_PORT", "8080"),
    WorkersStr = os:getenv("OMNICORN_WORKERS", "4"),
    AppPath = os:getenv("OMNICORN_APP", "demo:app"),

    Port = list_to_integer(PortStr),
    WorkerCount = list_to_integer(WorkersStr),

    io:format("[Omnicorn] Starting Control Plane on Port ~p with ~p workers wrapping ~s~n",
              [Port, WorkerCount, AppPath]),

    %% 2. Setup Cowboy Routes
    Dispatch = cowboy_router:compile([
        {'_', [{"/[...]", omn_http, []}]}
    ]),

    %% 3. Start Cowboy Listener
    {ok, _} = cowboy:start_clear(http_listener,
        [{port, Port}],
        #{env => #{dispatch => Dispatch}}
    ),

    %% 4. Start Supervision Tree
    omnicorn_sup:start_link(WorkerCount, AppPath).

stop(_State) ->
    ok.

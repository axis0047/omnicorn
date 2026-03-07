-module(omnicorn_app).
-behaviour(application).
-export([start/2, stop/1]).

start(_StartType, _StartArgs) ->
    PortStr = os:getenv("OMNICORN_PORT", "8080"),
    WorkersStr = os:getenv("OMNICORN_WORKERS", "4"),
    AppPath = os:getenv("OMNICORN_APP", "demo:app"), %%placeholder demo

    Port = list_to_integer(PortStr),
    WorkerCount = list_to_integer(WorkersStr),

    io:format("[Omnicorn] Starting Control Plane on Port ~p with ~p workers wrapping ~s~n",
              [Port, WorkerCount, AppPath]),

    %% Define Cowboy Routes: HTTP and WebSocket
    Dispatch = cowboy_router:compile([
        {'_', [
            %% HTTP route (matches everything not /ws)
            {<<"/[...:rest]">>, omn_http, []},
            %% WebSocket route (matches /ws or /ws/subpath)
            {<<"/ws/[...:rest]">>, omn_http, [{websocket_handler, omn_ws_handler}]}
        ]}
    ]),

    {ok, _} = cowboy:start_clear(http_listener,
        [{port, Port}],
        #{env => #{dispatch => Dispatch}}
    ),

    omnicorn_sup:start_link(WorkerCount, AppPath).

stop(_State) ->
    ok.

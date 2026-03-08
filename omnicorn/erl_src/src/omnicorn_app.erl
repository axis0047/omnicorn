-module(omnicorn_app).
-behaviour(application).
-export([start/2, stop/1]).

start(_StartType, _StartArgs) ->
    PortStr = os:getenv("OMNICORN_PORT", "8080"),
    WorkersStr = os:getenv("OMNICORN_WORKERS", "4"),
    AppPath = os:getenv("OMNICORN_APP", "demo:app"),

    Port = list_to_integer(PortStr),
    WorkerCount = list_to_integer(WorkersStr),

    io:format("[Omnicorn] Starting Control Plane on Port ~p...~n",[Port]),

    %% 1. Initialize Volatile Memory (Cache & Fast Tasks)
    ets:new(omnicorn_cache,[named_table, public, set, {read_concurrency, true}, {write_concurrency, true}]),
    ets:new(omnicorn_volatile_tasks,[named_table, public, ordered_set, {write_concurrency, true}]),

    %% 2. Initialize Persistent Storage on Disk (Mnesia for ETL workflows)
    %% Since the release script auto-starts mnesia, we must pause it to create the schema on first boot!
    application:stop(mnesia),
    mnesia:create_schema([node()]),
    application:start(mnesia),

    %% Create the persistent task table
    mnesia:create_table(omn_persistent_tasks, [
        {attributes,[id, name, payload, retries]},
        {disc_copies, [node()]} %% Write to local disk
    ]),

    %% 3. Start the Task Broker (Distributes jobs to multiplexed workers)
    omn_task_broker:start_link(),

    Dispatch = cowboy_router:compile([
        {'_', [
            {<<"/ws/[...]">>, omn_ws_handler,[]},
            {'_', omn_http,[]}
        ]}
    ]),

    {ok, _} = cowboy:start_clear(http_listener, [{port, Port}], #{env => #{dispatch => Dispatch}}),

    omnicorn_sup:start_link(WorkerCount, AppPath).

stop(_State) -> ok.

-module(omnicorn_app).
-behaviour(application).
-export([start/2, stop/1]).

start(_StartType, _StartArgs) ->
    Port = list_to_integer(os:getenv("OMNICORN_PORT", "8080")),
    WorkerCount = list_to_integer(os:getenv("OMNICORN_WORKERS", "4")),
    AppPath = os:getenv("OMNICORN_APP", "main:app"),

    %% Memory & Disk Initialization
    ets:new(omnicorn_cache,[named_table, public, set, {read_concurrency, true}, {write_concurrency, true}]),

    application:stop(mnesia),
    mnesia:create_schema([node()]),
    application:start(mnesia),

    mnesia:create_table(omn_sagas,[{attributes, [id, name, step, data]}, {disc_copies, [node()]}]),
    mnesia:create_table(omn_activities,[{attributes, [id, name, payload, retries]}, {disc_copies,[node()]}]),

    %% 🔥 THE FIX: Wait up to 5 seconds for Mnesia to load tables from disk into RAM.
    %% We MUST do this before starting the root supervisor, otherwise the child
    %% Task Broker and Actor Manager will try to query Mnesia before it's ready and crash!
    %% TODO: Change this 5000 configurable via configs.
    mnesia:wait_for_tables([omn_sagas, omn_activities], 5000),

    Dispatch = cowboy_router:compile([{'_',[{<<"/ws/[...]">>, omn_ws_handler, []}, {'_', omn_http,[]}]}]),
    {ok, _} = cowboy:start_clear(http_listener, [{port, Port}], #{env => #{dispatch => Dispatch}}),

    io:format("[Omnicorn 2.0] Actor-Model Control Plane Booted on ~p~n", [Port]),
    omnicorn_sup:start_link(WorkerCount, AppPath).

stop(_State) -> ok.

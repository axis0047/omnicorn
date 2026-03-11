-module(omnicorn_app).
-behaviour(application).
-export([start/2, stop/1]).

start(_StartType, _StartArgs) ->
    Port = list_to_integer(os:getenv("OMNICORN_PORT", "8080")),
    WorkerCount = list_to_integer(os:getenv("OMNICORN_WORKERS", "4")),
    AppPath = os:getenv("OMNICORN_APP", "main:app"),

    %% 1. Memory Initialization
    ets:new(omnicorn_cache,[named_table, public, set, {read_concurrency, true}, {write_concurrency, true}]),

    %% 2. 🛡️ BULLETPROOF MNESIA BOOT SEQUENCE
    application:stop(mnesia),
    %% We don't care if it returns already_exists, just ensure the schema is there.
    mnesia:create_schema([node()]),
    application:start(mnesia),

    %% Safe to call even if they already exist
    mnesia:create_table(omn_sagas,[{attributes, [id, name, step, data]}, {disc_copies, [node()]}]),
    mnesia:create_table(omn_activities,[{attributes,[id, name, payload, retries]}, {disc_copies,[node()]}]),

    %% Gracefully wait and log status to the console
    %% Update this to use a config for timeout, default 5000
    case mnesia:wait_for_tables([omn_sagas, omn_activities], 5000) of
        ok ->
            io:format("✅ Mnesia Persistent Disk-Tables loaded successfully.~n");
        {timeout, Bad} ->
            io:format("⚠️ Mnesia Timeout on: ~p~n", [Bad]);
        {error, Reason} ->
            io:format("🔥 Mnesia Error: ~p~n",[Reason])
    end,

    %% 3. Start the Web Server
    Dispatch = cowboy_router:compile([{'_',[{<<"/ws/[...]">>, omn_ws_handler, []}, {'_', omn_http,[]}]}]),
    {ok, _} = cowboy:start_clear(http_listener, [{port, Port}], #{env => #{dispatch => Dispatch}}),

    io:format("[Omnicorn 2.0] Actor-Model Control Plane Booted on ~p~n", [Port]),
    omnicorn_sup:start_link(WorkerCount, AppPath).

stop(_State) -> ok.

-module(omnicorn_app).
-behaviour(application).
-export([start/2, stop/1]).

start(_StartType, _StartArgs) ->
    Port = list_to_integer(os:getenv("OMNICORN_PORT", "8080")),
    WorkerCount = list_to_integer(os:getenv("OMNICORN_WORKERS", "4")),
    AppPath = os:getenv("OMNICORN_APP", "main:app"),

    %% 1. Memory Initialization
    ets:new(omnicorn_cache, [
        named_table, public, set,
        {read_concurrency, true}, {write_concurrency, true}
    ]),

    %% 2. Safe Mnesia Boot Sequence
    %% Step 1: Ensure schema exists BEFORE starting Mnesia
    ensure_schema(),
    
    %% Step 2: Start Mnesia
    application:start(mnesia),
    
    %% Step 3: Ensure tables exist (with distributed support)
    ensure_tables(),

    %% Step 4: Wait for tables with configurable timeout
    Tables = [omn_sagas, omn_activities],
    Timeout = list_to_integer(os:getenv("OMNICORN_MNESIA_TIMEOUT", "10000")),
    case mnesia:wait_for_tables(Tables, Timeout) of
        ok ->
            io:format("Mnesia persistent disk-tables loaded successfully~n");
        {timeout, Bad} ->
            io:format("Mnesia timeout waiting for tables: ~p~n", [Bad]),
            error({mnesia_timeout, Bad});
        {error, Reason} ->
            io:format("Mnesia error: ~p~n", [Reason]),
            error({mnesia_error, Reason})
    end,

    %% 3. Start the Web Server
    Dispatch = cowboy_router:compile([
        {'_', [
            {<<"/ws/[...]">>, omn_ws_handler, []},
            {'_', omn_http, []}
        ]}
    ]),
    {ok, _} = cowboy:start_clear(http_listener, [{port, Port}], #{
        env => #{dispatch => Dispatch}
    }),

    io:format("[Omnicorn 1.0] Actor-Model Control Plane booted on port ~p~n", [Port]),
    omnicorn_sup:start_link(WorkerCount, AppPath).

stop(_State) -> ok.

%% Ensure Mnesia schema exists (call BEFORE starting mnesia)
ensure_schema() ->
    try
        Result = mnesia:create_schema([node()]),
        case Result of
            ok ->
                io:format("Created Mnesia schema~n");
            {error, ErrorDetails} ->
                %% Check if it's an already_exists error
                ErrorStr = io_lib:format("~p", [ErrorDetails]),
                case string:find(ErrorStr, "already_exists") of
                    nomatch ->
                        io:format("Failed to create Mnesia schema: ~p~n", [ErrorDetails]),
                        error({schema_error, ErrorDetails});
                    _ ->
                        io:format("Mnesia schema already exists~n")
                end
        end
    catch
        _:_ ->
            io:format("Mnesia schema check complete~n")
    end.

%% Ensure tables exist
ensure_tables() ->
    %% Create omn_sagas table
    case mnesia:create_table(omn_sagas, [
        {attributes, [id, name, step, data]},
        {disc_copies, [node()]}
    ]) of
        {aborted, {already_exists, omn_sagas}} ->
            io:format("omn_sagas table already exists~n");
        {atomic, ok} ->
            io:format("Created omn_sagas table~n");
        {error, SagasReason} ->
            io:format("Could not create omn_sagas: ~p~n", [SagasReason])
    end,
    
    %% Create omn_activities table
    case mnesia:create_table(omn_activities, [
        {attributes, [id, name, payload, retries]},
        {disc_copies, [node()]}
    ]) of
        {aborted, {already_exists, omn_activities}} ->
            io:format("omn_activities table already exists~n");
        {atomic, ok} ->
            io:format("Created omn_activities table~n");
        {error, ActivitiesReason} ->
            io:format("Could not create omn_activities: ~p~n", [ActivitiesReason])
    end.

-module(omnicorn_sup).
-behaviour(supervisor).
-export([start_link/2, init/1]).

start_link(WorkerCount, AppPath) ->
    supervisor:start_link({local, ?MODULE}, ?MODULE, [WorkerCount, AppPath]).

init([WorkerCount, AppPath]) ->
    %% 1. Read Resilience Config from Env
    %% Default to 1000 crashes per 60 seconds (High Resilience)
    MaxR = list_to_integer(os:getenv("OMNICORN_MAX_RESTARTS", "1000")),
    MaxT = list_to_integer(os:getenv("OMNICORN_RESTART_PERIOD", "60")),

    SupFlags = #{
        strategy => one_for_one,
        intensity => MaxR,
        period => MaxT
    },

    %% 2. The Load Balancer (Router)
    RouterSpec = #{
        id => omn_router,
        start => {omn_router, start_link, [WorkerCount]},
        restart => permanent,
        type => worker
    },

    %% 3. The Worker Processes
    WorkerSpecs = [
        #{
            id => {omn_worker, I},
            start => {omn_worker, start_link, [list_to_binary(AppPath), I]},
            restart => permanent,
            shutdown => 2000,
            type => worker
        } || I <- lists:seq(1, WorkerCount)
    ],

    {ok, {SupFlags, [RouterSpec | WorkerSpecs]}}.

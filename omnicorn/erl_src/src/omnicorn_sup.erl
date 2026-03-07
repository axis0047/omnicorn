-module(omnicorn_sup).
-behaviour(supervisor).
-export([start_link/2, init/1]).

start_link(WorkerCount, AppPath) ->
    supervisor:start_link({local, ?MODULE}, ?MODULE, [WorkerCount, AppPath]).

init([WorkerCount, AppPath]) ->
    SupFlags = #{strategy => one_for_one, intensity => 10, period => 60},

    %% 1. The Load Balancer (Router)
    RouterSpec = #{
        id => omn_router,
        start => {omn_router, start_link, [WorkerCount]},
        restart => permanent,
        type => worker
    },

    %% 2. The Worker Processes
    %% We generate N worker specifications.
    WorkerSpecs = [
        #{
            id => {omn_worker, I},
            start => {omn_worker, start_link, [list_to_binary(AppPath), I]},
            restart => permanent,
            shutdown => 2000, % Wait 2s for graceful exit, then kill
            type => worker
        } || I <- lists:seq(1, WorkerCount)
    ],

    {ok, {SupFlags, [RouterSpec | WorkerSpecs]}}.

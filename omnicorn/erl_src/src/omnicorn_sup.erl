-module(omnicorn_sup).
-behaviour(supervisor).
-export([start_link/2, init/1]).

start_link(WorkerCount, AppPath) ->
    supervisor:start_link({local, ?MODULE}, ?MODULE, [WorkerCount, AppPath]).

init([WorkerCount, AppPath]) ->
    SupFlags = #{strategy => one_for_all, intensity => 1000, period => 60},

    WebSup = #{id => omn_web_sup, start => {omn_web_sup, start_link, [WorkerCount]}, type => supervisor},
    OrchSup = #{id => omn_orchestrator_sup, start => {omn_orchestrator_sup, start_link, []}, type => supervisor},

    WorkerSpecs =[#{id => {omn_worker, I}, start => {omn_worker, start_link, [list_to_binary(AppPath), I]}, type => worker} || I <- lists:seq(1, WorkerCount)],

    {ok, {SupFlags,[WebSup, OrchSup] ++ WorkerSpecs}}.

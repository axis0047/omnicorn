-module(omn_orchestrator_sup).
-behaviour(supervisor).
-export([start_link/0, init/1]).
start_link() -> supervisor:start_link({local, ?MODULE}, ?MODULE, []).
init([]) ->
    {ok, {#{strategy => one_for_all},[
        #{id => omn_workflow_actor_sup, start => {omn_workflow_actor_sup, start_link, []}, type => supervisor},
        #{id => omn_actor_manager, start => {omn_actor_manager, start_link,[]}},
        #{id => omn_task_broker, start => {omn_task_broker, start_link,[]}}
    ]}}.

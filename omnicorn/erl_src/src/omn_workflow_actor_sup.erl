-module(omn_workflow_actor_sup).
-behaviour(supervisor).
-export([start_link/0, init/1]).
start_link() -> supervisor:start_link({local, ?MODULE}, ?MODULE,[]).
init([]) -> {ok, {#{strategy => simple_one_for_one},[#{id => omn_workflow_actor, start => {omn_workflow_actor, start_link, []}, restart => temporary}]}}.

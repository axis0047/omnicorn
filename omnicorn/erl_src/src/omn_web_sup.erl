-module(omn_web_sup).
-behaviour(supervisor).
-export([start_link/1, init/1]).
start_link(Count) -> supervisor:start_link({local, ?MODULE}, ?MODULE, [Count]).
init([Count]) -> {ok, {#{strategy => one_for_one},[#{id => omn_router, start => {omn_router, start_link, [Count]}}]}}.

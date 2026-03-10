-module(omn_actor_manager).
-behaviour(gen_server).
-export([start_link/0, start_workflow/3, checkpoint_ack/4]).
-export([init/1, handle_call/3, handle_cast/2, handle_info/2]).

start_link() -> gen_server:start_link({local, ?MODULE}, ?MODULE, [],[]).
start_workflow(Id, Name, InitData) -> gen_server:cast(?MODULE, {start_wf, Id, Name, InitData}).
checkpoint_ack(WfId, NextStep, SleepMs, Data) -> gen_server:cast(?MODULE, {chk, WfId, NextStep, SleepMs, Data}).

init([]) ->
    ets:new(active_actors,[named_table, public, set]),
    {ok, #{}}.

handle_cast({start_wf, Id, Name, InitData}, State) ->
    {ok, Pid} = supervisor:start_child(omn_workflow_actor_sup, [Id, Name, <<"init">>, InitData]),
    ets:insert(active_actors, {Id, Pid}),
    {noreply, State};
handle_cast({chk, WfId, NextStep, SleepMs, Data}, State) ->
    case ets:lookup(active_actors, WfId) of
        [{_, Pid}] -> gen_server:cast(Pid, {checkpoint, NextStep, SleepMs, Data});
        _ -> ok
    end, {noreply, State}.
handle_call(_, _, S) -> {reply, ok, S}.
handle_info(_, S) -> {noreply, S}.

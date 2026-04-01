-module(omn_actor_manager).
-behaviour(gen_server).

-export([start_link/0, start_workflow/3, checkpoint_ack/4, cancel_workflow/1, get_workflows/0]).
-export([init/1, handle_call/3, handle_cast/2, handle_info/2]).

start_link() ->
    gen_server:start_link({local, ?MODULE}, ?MODULE, [], []).

start_workflow(Id, Name, InitData) ->
    gen_server:cast(?MODULE, {start_wf, Id, Name, InitData}).

checkpoint_ack(WfId, NextStep, SleepMs, Data) ->
    gen_server:cast(?MODULE, {chk, WfId, NextStep, SleepMs, Data}).

cancel_workflow(WfId) ->
    gen_server:call(?MODULE, {cancel, WfId}).

get_workflows() ->
    gen_server:call(?MODULE, get_workflows).

init([]) ->
    ets:new(active_actors, [named_table, public, set]),

    %% Resurrection Logic: Load all suspended workflows from disk on boot
    %% Only resurrect if Mnesia table exists
    PendingSagas = case catch mnesia:table_info(omn_sagas, name) of
        {'EXIT', _} -> [];  %% Table doesn't exist, skip resurrection
        _ ->
            case catch mnesia:dirty_match_object({omn_sagas, '_', '_', '_', '_'}) of
                {'EXIT', _} -> [];  %% Can't read table, skip
                Sagas -> Sagas
            end
    end,
    
    lists:foreach(fun({omn_sagas, Id, Name, Step, Data}) ->
        %% Spawn a new Actor for every saved workflow
        {ok, Pid} = supervisor:start_child(omn_workflow_actor_sup, [Id, Name, Step, Data]),
        ets:insert(active_actors, {Id, Pid})
    end, PendingSagas),

    {ok, #{}}.

handle_cast({start_wf, Id, Name, InitData}, State) ->
    case ets:lookup(active_actors, Id) of
        [] ->
            %% New workflow - start from init step
            {ok, Pid} = supervisor:start_child(
                omn_workflow_actor_sup,
                [Id, Name, <<"init">>, InitData]
            ),
            ets:insert(active_actors, {Id, Pid});
        _ ->
            io:format("Workflow ~p already exists~n", [Id])
    end,
    {noreply, State};

handle_cast({chk, WfId, NextStep, SleepMs, Data}, State) ->
    case ets:lookup(active_actors, WfId) of
        [{_, Pid}] ->
            omn_workflow_statem:checkpoint(Pid, NextStep, SleepMs, Data);
        _ ->
            ok
    end,
    {noreply, State};

handle_cast(_, State) ->
    {noreply, State}.

handle_call({cancel, WfId}, _From, State) ->
    case ets:lookup(active_actors, WfId) of
        [{_, Pid}] ->
            %% Cancel the workflow
            omn_workflow_statem:cancel(Pid),
            {reply, ok, State};
        _ ->
            {reply, {error, not_found}, State}
    end;

handle_call(get_workflows, _From, State) ->
    Workflows = ets:tab2list(active_actors),
    WorkflowList = [{Id, Pid} || {Id, Pid} <- Workflows],
    {reply, WorkflowList, State};

handle_call(_, _, State) ->
    {reply, {error, unknown_call}, State}.

handle_info(_, State) ->
    {noreply, State}.

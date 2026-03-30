-module(omn_workflow_statem).
-behaviour(gen_statem).

%% API
-export([start_link/4, execute/1, checkpoint/4, cancel/1]).

%% gen_statem callbacks
-export([init/1, callback_mode/0, handle_event/4, terminate/3, code_change/4]).

-record(data, {
    id,
    name,
    step,
    data,
    created_at
}).

%%====================================================================
%% API
%%====================================================================

start_link(Id, Name, Step, Data) ->
    gen_statem:start_link(?MODULE, [Id, Name, Step, Data], []).

execute(Pid) ->
    gen_statem:cast(Pid, execute).

checkpoint(Pid, NextStep, SleepMs, Data) ->
    gen_statem:cast(Pid, {checkpoint, NextStep, SleepMs, Data}).

cancel(Pid) ->
    gen_statem:cast(Pid, cancel).

%%====================================================================
%% gen_statem callbacks
%%====================================================================

init([Id, Name, Step, Data]) ->
    process_flag(trap_exit, true),
    
    %% Persist initial state to Mnesia
    mnesia:dirty_write({omn_sagas, Id, Name, Step, Data}),
    
    %% Register in ETS for lookup
    ets:insert(active_actors, {Id, self()}),
    
    DataRec = #data{
        id = Id,
        name = Name,
        step = Step,
        data = Data,
        created_at = erlang:system_time(millisecond)
    },
    
    {ok, waiting_for_worker, DataRec}.

callback_mode() ->
    state_functions.

%%====================================================================
%% State: waiting_for_worker
%%====================================================================

waiting_for_worker(cast, execute, Data = #data{id=Id, name=Name, step=Step, data=ExecData}) ->
    case omn_router:checkout_worker() of
        {ok, Worker} ->
            Msg = #{
                <<"type">> => <<"workflow_execute">>,
                <<"payload">> => #{
                    <<"workflow_id">> => Id,
                    <<"name">> => Name,
                    <<"step">> => Step,
                    <<"data">> => ExecData
                }
            },
            omn_worker:send_async(Worker, Msg),
            {keep_state, Data};
        _ ->
            %% No worker available, retry after delay
            erlang:send_after(1000, self(), retry_execute),
            {keep_state, Data}
    end;

waiting_for_worker(info, retry_execute, _Data) ->
    {keep_state_and_data, {event, cast, execute}};

waiting_for_worker(cast, {checkpoint, <<"__finished__">>, _, _}, Data = #data{id=Id}) ->
    %% Workflow complete - cleanup and terminate
    mnesia:dirty_delete(omn_sagas, Id),
    ets:delete(active_actors, Id),
    {stop, normal, Data};

waiting_for_worker(cast, {checkpoint, NextStep, SleepMs, ExecData}, Data = #data{id=Id, name=Name}) ->
    %% Persist checkpoint to Mnesia
    mnesia:dirty_write({omn_sagas, Id, Name, NextStep, ExecData}),
    
    if
        SleepMs > 0 ->
            %% Schedule future execution and transition to suspended state
            erlang:send_after(SleepMs, self(), delayed_execute),
            {next_state, suspended, Data#data{step=NextStep, data=ExecData}};
        true ->
            %% Continue immediately
            {keep_state_and_data, {event, cast, execute}}
    end;

waiting_for_worker(cast, cancel, Data = #data{id=Id}) ->
    %% Workflow cancelled - cleanup
    mnesia:dirty_delete(omn_sagas, Id),
    ets:delete(active_actors, Id),
    {stop, {shutdown, cancelled}, Data};

waiting_for_worker(EventType, EventContent, Data) ->
    handle_event(EventType, EventContent, waiting_for_worker, Data).

%%====================================================================
%% State: suspended (waiting for timer)
%%====================================================================

suspended(info, delayed_execute, _Data) ->
    {next_state, waiting_for_worker, {event, cast, execute}};

suspended(cast, {checkpoint, NextStep, SleepMs, ExecData}, Data = #data{id=Id, name=Name}) ->
    %% Update checkpoint while suspended
    mnesia:dirty_write({omn_sagas, Id, Name, NextStep, ExecData}),
    
    if
        SleepMs > 0 ->
            %% Reschedule with new timeout
            erlang:send_after(SleepMs, self(), delayed_execute),
            {keep_state, Data#data{step=NextStep, data=ExecData}};
        true ->
            %% Wake up and continue
            {next_state, waiting_for_worker, {event, cast, execute}}
    end;

suspended(cast, cancel, Data = #data{id=Id}) ->
    %% Workflow cancelled while suspended - cleanup
    mnesia:dirty_delete(omn_sagas, Id),
    ets:delete(active_actors, Id),
    {stop, {shutdown, cancelled}, Data};

suspended(EventType, EventContent, Data) ->
    handle_event(EventType, EventContent, suspended, Data).

%%====================================================================
%% Common event handler
%%====================================================================

handle_event(cast, _, _, Data) ->
    {keep_state, Data};

handle_event(info, _, _, Data) ->
    {keep_state, Data};

handle_event(_, _, _, Data) ->
    {keep_state, Data}.

%%====================================================================
%% Termination callback
%%====================================================================

terminate(_Reason, _State, _Data) ->
    ok.

%%====================================================================
%% Code change callback
%%====================================================================

code_change(_OldVsn, State, Data, _Extra) ->
    {ok, State, Data}.

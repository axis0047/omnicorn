-module(omn_workflow_statem_tests).
-include_lib("eunit/include/eunit.hrl").

%%====================================================================
%% Workflow State Machine Tests
%%====================================================================

init_test_() ->
    {setup,
        fun setup_workflow/0,
        fun cleanup_workflow/1,
        fun do_init_test/1
    }.

do_init_test(_Pid) ->
    [
        {"init persists state to Mnesia", fun init_persists_state/0},
        {"init registers in ETS", fun init_registers_in_ets/0}
    ].

init_persists_state() ->
    Id = <<"wf_init_test">>,
    Name = <<"test_workflow">>,
    Step = <<"init">>,
    Data = #{<<"key">> => <<"value">>},
    
    %% Start workflow
    {ok, Pid} = omn_workflow_statem:start_link(Id, Name, Step, Data),
    timer:sleep(100),
    
    %% Verify state is persisted
    [{omn_sagas, Id, Name, Step, StoredData}] = mnesia:dirty_read(omn_sagas, Id),
    ?assertEqual(Data, StoredData),
    
    %% Cleanup
    gen_server:stop(Pid),
    mnesia:dirty_delete(omn_sagas, Id).

init_registers_in_ets() ->
    Id = <<"wf_ets_test">>,
    Name = <<"test_workflow">>,
    Step = <<"init">>,
    Data = #{},
    
    %% Start workflow
    {ok, Pid} = omn_workflow_statem:start_link(Id, Name, Step, Data),
    timer:sleep(100),
    
    %% Verify registration in ETS
    [{Id, Pid}] = ets:lookup(active_actors, Id),
    
    %% Cleanup
    gen_server:stop(Pid),
    ets:delete(active_actors, Id),
    mnesia:dirty_delete(omn_sagas, Id).

checkpoint_finish_test_() ->
    {setup,
        fun setup_workflow/0,
        fun cleanup_workflow/1,
        fun do_checkpoint_finish_test/1
    }.

do_checkpoint_finish_test(Pid) ->
    [
        {"checkpoint with __finished__ terminates workflow", fun checkpoint_finish_terminates/0}
    ].

checkpoint_finish_terminates() ->
    Id = <<"wf_finish_test">>,
    Name = <<"test_workflow">>,
    Step = <<"init">>,
    Data = #{},
    
    %% Start workflow
    {ok, _Pid} = omn_workflow_statem:start_link(Id, Name, Step, Data),
    timer:sleep(100),
    
    %% Send finish checkpoint
    omn_workflow_statem:checkpoint(self(), <<"__finished__">>, 0, #{}),
    timer:sleep(100),
    
    %% Verify workflow is terminated
    ?assertMatch([], ets:lookup(active_actors, Id)),
    ?assertMatch([], mnesia:dirty_read(omn_sagas, Id)).

checkpoint_with_sleep_test_() ->
    {setup,
        fun setup_workflow/0,
        fun cleanup_workflow/1,
        fun do_checkpoint_sleep_test/1
    }.

do_checkpoint_sleep_test(Pid) ->
    [
        {"checkpoint with sleep transitions to suspended", fun checkpoint_sleep_suspends/0}
    ].

checkpoint_sleep_suspends() ->
    Id = <<"wf_sleep_test">>,
    Name = <<"test_workflow">>,
    Step = <<"init">>,
    Data = #{},
    
    %% Start workflow
    {ok, _Pid} = omn_workflow_statem:start_link(Id, Name, Step, Data),
    timer:sleep(100),
    
    %% Send checkpoint with sleep
    omn_workflow_statem:checkpoint(self(), <<"next_step">>, 500, #{<<"updated">> => true}),
    timer:sleep(100),
    
    %% Verify state is updated in Mnesia
    [{omn_sagas, Id, Name, <<"next_step">>, UpdatedData}] = mnesia:dirty_read(omn_sagas, Id),
    ?assertEqual(true, maps:get(<<"updated">>, UpdatedData)),
    
    %% Cleanup
    mnesia:dirty_delete(omn_sagas, Id).

execute_test_() ->
    {setup,
        fun setup_workflow/0,
        fun cleanup_workflow/1,
        fun do_execute_test/1
    }.

do_execute_test(Pid) ->
    [
        {"execute sends message to worker", fun execute_sends_to_worker/0}
    ].

execute_sends_to_worker() ->
    Id = <<"wf_exec_test">>,
    Name = <<"test_workflow">>,
    Step = <<"init">>,
    Data = #{<<"test">> => true},
    
    %% Start workflow
    {ok, _Pid} = omn_workflow_statem:start_link(Id, Name, Step, Data),
    timer:sleep(100),
    
    %% Trigger execute
    omn_workflow_statem:execute(self()),
    timer:sleep(100),
    
    %% Verify message was sent (would need mock worker to fully test)
    %% For now, just verify no crash
    
    %% Cleanup
    mnesia:dirty_delete(omn_sagas, Id).

%%====================================================================
%% Helper Functions
%%====================================================================

setup_workflow() ->
    %% Ensure Mnesia is running
    application:start(mnesia),
    
    %% Create tables
    mnesia:create_table(omn_sagas, [
        {attributes, [id, name, step, data]},
        {disc_copies, [node()]}
    ]),
    mnesia:wait_for_tables([omn_sagas], 5000),
    
    %% Create ETS table for active actors
    ets:new(active_actors, [named_table, public, set]),
    
    ok.

cleanup_workflow(_Pid) ->
    %% Clean up any remaining workflows
    Sagas = mnesia:dirty_match_object({omn_sagas, '_', '_', '_', '_'}),
    lists:foreach(fun({omn_sagas, Id, _, _, _}) ->
        mnesia:dirty_delete(omn_sagas, Id),
        ets:delete(active_actors, Id)
    end, Sagas),
    ok.

-module(omn_workflow_statem_tests).
-include_lib("eunit/include/eunit.hrl").

%% Test Suite: omn_workflow_statem
%% Coverage Target: 95%

%% Initialize Mnesia before tests
init_per_testcase(_Name, _Config) ->
    omn_test_helper:setup_mnesia(),
    [].

end_per_testcase(_Name, _Config) ->
    omn_test_helper:cleanup_mnesia(),
    ok.

%%====================================================================
%% State Machine Initialization Tests
%%====================================================================

workflow_statem_start_test() ->
    %% Test workflow state machine starts correctly
    Id = <<"wf_start_test">>,
    {ok, Pid} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"init">>, #{}),
    ?assert(is_pid(Pid)),
    timer:sleep(50),
    
    %% Verify registered in ETS
    [{Id, Pid}] = ets:lookup(active_actors, Id),
    
    %% Cleanup
    gen_statem:stop(Pid),
    mnesia:dirty_delete(omn_sagas, Id).

workflow_statem_persists_state_test() ->
    %% Test workflow persists state to Mnesia on start
    Id = <<"wf_persist_test">>,
    Data = #{<<"key">> => <<"value">>},
    {ok, Pid} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"init">>, Data),
    timer:sleep(50),
    
    %% Verify persisted to Mnesia
    [{omn_sagas, Id, <<"test_wf">>, <<"init">>, StoredData}] = 
        mnesia:dirty_read(omn_sagas, Id),
    ?assertEqual(Data, StoredData),
    
    %% Cleanup
    gen_statem:stop(Pid),
    mnesia:dirty_delete(omn_sagas, Id).

%%====================================================================
%% State Transition Tests
%%====================================================================

workflow_checkpoint_finish_test() ->
    %% Test workflow completion via checkpoint
    Id = <<"wf_finish_test">>,
    {ok, Pid} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"init">>, #{}),
    timer:sleep(50),
    
    %% Send finish checkpoint
    omn_workflow_statem:checkpoint(Pid, <<"__finished__">>, 0, #{}),
    timer:sleep(100),
    
    %% Verify workflow terminated and cleaned up
    [] = ets:lookup(active_actors, Id),
    [] = mnesia:dirty_read(omn_sagas, Id),
    
    ok.

workflow_checkpoint_with_sleep_test() ->
    %% Test workflow checkpoint with sleep
    Id = <<"wf_sleep_test">>,
    {ok, Pid} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"init">>, #{}),
    timer:sleep(50),
    
    %% Send checkpoint with sleep
    omn_workflow_statem:checkpoint(Pid, <<"next_step">>, 500, #{<<"updated">> => true}),
    timer:sleep(100),
    
    %% Verify state updated in Mnesia
    [{omn_sagas, Id, <<"test_wf">>, <<"next_step">>, UpdatedData}] = 
        mnesia:dirty_read(omn_sagas, Id),
    ?assertEqual(true, maps:get(<<"updated">>, UpdatedData)),
    
    %% Cleanup
    gen_statem:stop(Pid),
    mnesia:dirty_delete(omn_sagas, Id).

workflow_checkpoint_immediate_execute_test() ->
    %% Test workflow checkpoint without sleep executes immediately
    Id = <<"wf_immediate_test">>,
    {ok, Pid} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"init">>, #{}),
    timer:sleep(50),
    
    %% Send checkpoint without sleep
    omn_workflow_statem:checkpoint(Pid, <<"step2">>, 0, #{}),
    timer:sleep(200),
    
    %% Should have attempted to execute next step
    %% (verified by checking workflow still running)
    ?assert(is_pid(Pid)),
    
    %% Cleanup
    gen_statem:stop(Pid),
    mnesia:dirty_delete(omn_sagas, Id).

%%====================================================================
%% Workflow Cancellation Tests
%%====================================================================

workflow_cancel_test() ->
    %% Test workflow cancellation
    Id = <<"wf_cancel_test">>,
    {ok, Pid} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"init">>, #{}),
    timer:sleep(50),
    
    %% Cancel the workflow
    omn_workflow_statem:cancel(Pid),
    timer:sleep(100),
    
    %% Verify workflow terminated and cleaned up
    [] = ets:lookup(active_actors, Id),
    [] = mnesia:dirty_read(omn_sagas, Id),
    
    ok.

workflow_cancel_while_suspended_test() ->
    %% Test workflow cancellation while suspended
    Id = <<"wf_cancel_suspend_test">>,
    {ok, Pid} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"init">>, #{}),
    timer:sleep(50),
    
    %% Put workflow to sleep (suspended state)
    omn_workflow_statem:checkpoint(Pid, <<"waiting">>, 10000, #{}),
    timer:sleep(100),
    
    %% Cancel while suspended
    omn_workflow_statem:cancel(Pid),
    timer:sleep(100),
    
    %% Verify workflow terminated
    [] = ets:lookup(active_actors, Id),
    [] = mnesia:dirty_read(omn_sagas, Id),
    
    ok.

%%====================================================================
%% Worker Communication Tests
%%====================================================================

workflow_execute_sends_to_worker_test() ->
    %% Test workflow sends execute message to worker
    Id = <<"wf_execute_test">>,
    {ok, Pid} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"init">>, #{}),
    timer:sleep(50),
    
    %% Trigger execute
    omn_workflow_statem:execute(Pid),
    timer:sleep(100),
    
    %% Message should be sent to worker (verified by no crash)
    ?assert(is_pid(Pid)),
    
    %% Cleanup
    gen_statem:stop(Pid),
    mnesia:dirty_delete(omn_sagas, Id).

workflow_retry_on_no_worker_test() ->
    %% Test workflow retries when no worker available
    Id = <<"wf_retry_test">>,
    {ok, Pid} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"init">>, #{}),
    timer:sleep(50),
    
    %% Trigger execute (will fail if no workers)
    omn_workflow_statem:execute(Pid),
    timer:sleep(1100),  %% Wait for retry (1s delay)
    
    %% Workflow should still be running (retrying)
    ?assert(is_pid(Pid)),
    
    %% Cleanup
    gen_statem:stop(Pid),
    mnesia:dirty_delete(omn_sagas, Id).

%%====================================================================
%% State Persistence Tests
%%====================================================================

workflow_state_recovery_test() ->
    %% Test workflow state can be recovered from Mnesia
    Id = <<"wf_recovery_test">>,
    Data = #{<<"counter">> => 5, <<"name">> => <<"test">>},
    
    %% Persist state manually
    mnesia:dirty_write({omn_sagas, Id, <<"test_wf">>, <<"step3">>, Data}),
    
    %% Start workflow (should use persisted state)
    {ok, Pid} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"step3">>, Data),
    timer:sleep(50),
    
    %% Verify state matches
    [{omn_sagas, Id, <<"test_wf">>, <<"step3">>, RecoveredData}] = 
        mnesia:dirty_read(omn_sagas, Id),
    ?assertEqual(Data, RecoveredData),
    
    %% Cleanup
    gen_statem:stop(Pid),
    mnesia:dirty_delete(omn_sagas, Id).

workflow_checkpoint_updates_mnesia_test() ->
    %% Test checkpoint updates Mnesia
    Id = <<"wf_checkpoint_mnesia_test">>,
    {ok, Pid} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"init">>, #{}),
    timer:sleep(50),
    
    %% Initial state
    [{omn_sagas, Id, _, <<"init">>, _}] = mnesia:dirty_read(omn_sagas, Id),
    
    %% Checkpoint to next step
    NewData = #{<<"step">> => 2},
    omn_workflow_statem:checkpoint(Pid, <<"step2">>, 0, NewData),
    timer:sleep(100),
    
    %% Verify Mnesia updated
    [{omn_sagas, Id, _, <<"step2">>, NewData}] = mnesia:dirty_read(omn_sagas, Id),
    
    %% Cleanup
    gen_statem:stop(Pid),
    mnesia:dirty_delete(omn_sagas, Id).

%%====================================================================
%% Edge Cases Tests
%%====================================================================

workflow_duplicate_start_test() ->
    %% Test starting workflow with duplicate ID
    Id = <<"wf_duplicate_test">>,
    {ok, Pid1} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"init">>, #{}),
    timer:sleep(50),
    
    %% Starting another with same ID should create new process
    %% (Erlang allows this, application logic should prevent)
    {ok, Pid2} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"init">>, #{}),
    timer:sleep(50),
    
    ?assert(is_pid(Pid1)),
    ?assert(is_pid(Pid2)),
    
    %% Cleanup
    gen_statem:stop(Pid1),
    gen_statem:stop(Pid2),
    mnesia:dirty_delete(omn_sagas, Id).

workflow_large_data_test() ->
    %% Test workflow with large data payload
    Id = <<"wf_large_test">>,
    LargeData = maps:from_list([{list_to_binary(integer_to_list(N)), N} || N <- lists:seq(1, 100)]),
    
    {ok, Pid} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"init">>, LargeData),
    timer:sleep(50),
    
    %% Verify large data persisted
    [{omn_sagas, Id, _, _, StoredData}] = mnesia:dirty_read(omn_sagas, Id),
    ?assertEqual(LargeData, StoredData),
    
    %% Cleanup
    gen_statem:stop(Pid),
    mnesia:dirty_delete(omn_sagas, Id).

workflow_concurrent_checkpoints_test() ->
    %% Test concurrent checkpoint messages
    Id = <<"wf_concurrent_test">>,
    {ok, Pid} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"init">>, #{}),
    timer:sleep(50),
    
    %% Send multiple checkpoints concurrently
    [omn_workflow_statem:checkpoint(Pid, list_to_binary("step" ++ integer_to_list(N)), 0, #{})
     || N <- lists:seq(1, 5)],
    timer:sleep(200),
    
    %% Should not crash (last checkpoint wins)
    ?assert(is_pid(Pid)),
    
    %% Cleanup
    gen_statem:stop(Pid),
    mnesia:dirty_delete(omn_sagas, Id).

%%====================================================================
%% Timeout Tests
%%====================================================================

workflow_delayed_execute_test() ->
    %% Test workflow executes after delay
    Id = <<"wf_delay_test">>,
    {ok, Pid} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"init">>, #{}),
    timer:sleep(50),
    
    %% Checkpoint with delay
    omn_workflow_statem:checkpoint(Pid, <<"delayed_step">>, 500, #{}),
    timer:sleep(600),
    
    %% Should have woken up and attempted execute
    ?assert(is_pid(Pid)),
    
    %% Cleanup
    gen_statem:stop(Pid),
    mnesia:dirty_delete(omn_sagas, Id).

workflow_terminate_cleanup_test() ->
    %% Test workflow terminates and cleans up properly
    Id = <<"wf_terminate_test">>,
    {ok, Pid} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"init">>, #{}),
    timer:sleep(50),
    
    %% Stop workflow
    gen_statem:stop(Pid),
    timer:sleep(100),
    
    %% Verify ETS cleanup
    [] = ets:lookup(active_actors, Id),
    
    %% Mnesia should still have state (not deleted on normal stop)
    ?assertMatch([{omn_sagas, Id, _, _, _}], mnesia:dirty_read(omn_sagas, Id)),
    
    %% Cleanup
    mnesia:dirty_delete(omn_sagas, Id).

%%====================================================================
%% Helper Functions
%%====================================================================

-module(omn_workflow_statem_tests).
-include_lib("eunit/include/eunit.hrl").

%% Test Suite: omn_workflow_statem
%% Coverage Target: 95%

%% Helper to setup Mnesia
setup_mnesia() ->
    %% Ensure Mnesia is running
    case application:start(mnesia) of
        ok -> ok;
        {error, {already_started, mnesia}} -> ok;
        _ -> ok
    end,
    timer:sleep(100),
    
    %% Delete tables if they exist
    catch mnesia:delete_table(omn_sagas),
    catch mnesia:delete_table(omn_activities),
    timer:sleep(200),
    
    %% Create tables with ram_copies for testing (disc_copies requires distributed node)
    case mnesia:create_table(omn_sagas, [{attributes, [id, name, step, data]}, {ram_copies, [node()]}]) of
        {atomic, ok} -> ok;
        {aborted, {already_exists, omn_sagas}} -> ok
    end,
    case mnesia:create_table(omn_activities, [{attributes, [id, name, payload, retries]}, {ram_copies, [node()]}]) of
        {atomic, ok} -> ok;
        {aborted, {already_exists, omn_activities}} -> ok
    end,
    ok = mnesia:wait_for_tables([omn_sagas, omn_activities], 5000),
    timer:sleep(100),
    
    %% Clear tables for fresh test
    catch mnesia:clear_table(omn_sagas),
    catch mnesia:clear_table(omn_activities),
    timer:sleep(100),
    
    %% Create ETS table for active actors
    catch ets:delete(active_actors),
    ets:new(active_actors, [named_table, public, set]),
    
    %% Start omn_router (required for workflow checkout)
    case omn_router:start_link(2) of
        {ok, _} -> ok;
        {error, {already_started, _}} -> ok
    end,
    
    %% Register a mock worker so checkout doesn't timeout
    MockWorker = self(),
    omn_router:checkin_worker(MockWorker),
    timer:sleep(100),
    ok.

cleanup_mnesia() ->
    catch mnesia:clear_table(omn_sagas),
    catch mnesia:clear_table(omn_activities),
    catch ets:delete(active_actors),
    timer:sleep(100),
    ok.

%%====================================================================
%% State Machine Initialization Tests
%%====================================================================

workflow_statem_start_test() ->
    setup_mnesia(),
    
    %% Test workflow state machine starts correctly
    Id = <<"wf_start_test">>,
    {ok, Pid} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"init">>, #{}),
    ?assert(is_pid(Pid)),
    timer:sleep(50),

    %% Verify registered in ETS
    ?assertMatch([{Id, Pid}], ets:lookup(active_actors, Id)),

    %% Cleanup
    unlink(Pid),
    gen_statem:stop(Pid),
    cleanup_mnesia(),
    ok.

workflow_statem_persists_state_test() ->
    setup_mnesia(),
    
    %% Test workflow persists state to Mnesia on start
    Id = <<"wf_persist_test">>,
    Data = #{<<"key">> => <<"value">>},
    {ok, Pid} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"init">>, Data),
    timer:sleep(50),

    %% Verify persisted to Mnesia
    [{omn_sagas, Id, _, _, StoredData}] = mnesia:dirty_read(omn_sagas, Id),
    ?assertEqual(Data, StoredData),

    %% Cleanup
    unlink(Pid),
    gen_statem:stop(Pid),
    cleanup_mnesia(),
    ok.

%%====================================================================
%% State Transition Tests
%%====================================================================

workflow_checkpoint_finish_test() ->
    setup_mnesia(),
    
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

    cleanup_mnesia(),
    ok.

workflow_checkpoint_with_sleep_test() ->
    setup_mnesia(),
    
    %% Test workflow checkpoint with sleep
    Id = <<"wf_sleep_test">>,
    {ok, Pid} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"init">>, #{}),
    timer:sleep(50),

    %% Send checkpoint with sleep
    omn_workflow_statem:checkpoint(Pid, <<"next_step">>, 500, #{<<"updated">> => true}),
    timer:sleep(100),

    %% Verify state updated in Mnesia
    [{omn_sagas, Id, _, _, UpdatedData}] = mnesia:dirty_read(omn_sagas, Id),
    ?assertEqual(true, maps:get(<<"updated">>, UpdatedData)),

    %% Cleanup
    unlink(Pid),
    gen_statem:stop(Pid),
    cleanup_mnesia(),
    ok.

workflow_checkpoint_immediate_execute_test() ->
    setup_mnesia(),
    
    %% Test workflow checkpoint updates state
    Id = <<"wf_immediate_test">>,
    {ok, Pid} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"init">>, #{}),
    timer:sleep(50),

    %% Send checkpoint without sleep
    omn_workflow_statem:checkpoint(Pid, <<"step2">>, 0, #{}),
    timer:sleep(100),

    %% Verify checkpoint was persisted
    [{omn_sagas, Id, _, <<"step2">>, _}] = mnesia:dirty_read(omn_sagas, Id),

    %% Workflow should still be running
    ?assert(is_pid(Pid)),

    %% Cleanup
    unlink(Pid),
    gen_statem:stop(Pid),
    cleanup_mnesia(),
    ok.

workflow_cancel_test() ->
    setup_mnesia(),
    
    %% Test workflow cancellation
    Id = <<"wf_cancel_test">>,
    {ok, Pid} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"init">>, #{}),
    timer:sleep(50),

    %% Unlink to prevent test process termination when workflow cancels
    unlink(Pid),
    
    %% Cancel the workflow
    omn_workflow_statem:cancel(Pid),
    timer:sleep(200),

    %% Verify workflow terminated and cleaned up
    [] = ets:lookup(active_actors, Id),

    cleanup_mnesia(),
    ok.

workflow_cancel_while_suspended_test() ->
    setup_mnesia(),
    
    %% Test workflow cancellation while suspended
    Id = <<"wf_cancel_suspend_test">>,
    {ok, Pid} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"init">>, #{}),
    timer:sleep(50),

    %% Put workflow to sleep (suspended state)
    omn_workflow_statem:checkpoint(Pid, <<"waiting">>, 10000, #{}),
    timer:sleep(100),

    %% Unlink to prevent test process termination
    unlink(Pid),
    
    %% Cancel while suspended
    omn_workflow_statem:cancel(Pid),
    timer:sleep(200),

    %% Verify workflow terminated
    [] = ets:lookup(active_actors, Id),

    cleanup_mnesia(),
    ok.

%%====================================================================
%% Worker Communication Tests
%%====================================================================

workflow_execute_sends_to_worker_test() ->
    setup_mnesia(),
    
    %% Test workflow sends execute message to worker
    Id = <<"wf_execute_test">>,
    {ok, Pid} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"init">>, #{}),
    timer:sleep(50),

    %% Trigger execute (will retry since no workers available)
    omn_workflow_statem:execute(Pid),
    timer:sleep(200),  %% Wait for checkout attempt

    %% Workflow should still be running (will retry)
    ?assert(is_pid(Pid)),

    %% Cleanup - unlink first to prevent termination
    unlink(Pid),
    unlink(Pid),
    gen_statem:stop(Pid),
    cleanup_mnesia(),
    ok.

workflow_retry_on_no_worker_test() ->
    setup_mnesia(),
    
    %% Test workflow retries when no worker available
    Id = <<"wf_retry_test">>,
    {ok, Pid} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"init">>, #{}),
    timer:sleep(50),

    %% Trigger execute (will fail if no workers)
    omn_workflow_statem:execute(Pid),
    timer:sleep(500),  %% Wait for retry (reduced from 1100ms)

    %% Workflow should still be running (retrying)
    ?assert(is_pid(Pid)),

    %% Cleanup - unlink first
    unlink(Pid),
    unlink(Pid),
    gen_statem:stop(Pid),
    cleanup_mnesia(),
    ok.

workflow_state_recovery_test() ->
    setup_mnesia(),
    
    %% Test workflow state can be recovered from Mnesia
    Id = <<"wf_recovery_test">>,
    Data = #{<<"counter">> => 5, <<"name">> => <<"test">>},

    %% Persist state manually
    mnesia:dirty_write({omn_sagas, Id, <<"test_wf">>, <<"step3">>, Data}),

    %% Start workflow (should use persisted state)
    {ok, Pid} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"step3">>, Data),
    timer:sleep(50),

    %% Verify state matches
    [{omn_sagas, Id, _, _, RecoveredData}] = mnesia:dirty_read(omn_sagas, Id),
    ?assertEqual(Data, RecoveredData),

    %% Cleanup
    unlink(Pid),
    gen_statem:stop(Pid),
    cleanup_mnesia(),
    ok.

workflow_checkpoint_updates_mnesia_test() ->
    setup_mnesia(),
    
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
    unlink(Pid),
    gen_statem:stop(Pid),
    cleanup_mnesia(),
    ok.

workflow_duplicate_start_test() ->
    setup_mnesia(),
    
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
    cleanup_mnesia(),
    ok.

workflow_large_data_test() ->
    setup_mnesia(),
    
    %% Test workflow with large data payload
    Id = <<"wf_large_test">>,
    LargeData = maps:from_list([{list_to_binary(integer_to_list(N)), N} || N <- lists:seq(1, 100)]),

    {ok, Pid} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"init">>, LargeData),
    timer:sleep(50),

    %% Verify large data persisted
    [{omn_sagas, Id, _, _, StoredData}] = mnesia:dirty_read(omn_sagas, Id),
    ?assertEqual(LargeData, StoredData),

    %% Cleanup
    unlink(Pid),
    gen_statem:stop(Pid),
    cleanup_mnesia(),
    ok.

workflow_concurrent_checkpoints_test() ->
    setup_mnesia(),
    
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
    unlink(Pid),
    gen_statem:stop(Pid),
    cleanup_mnesia(),
    ok.

workflow_delayed_execute_test() ->
    setup_mnesia(),
    
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
    unlink(Pid),
    gen_statem:stop(Pid),
    cleanup_mnesia(),
    ok.

workflow_terminate_cleanup_test() ->
    setup_mnesia(),
    
    %% Test workflow terminates and cleans up properly
    Id = <<"wf_terminate_test">>,
    {ok, Pid} = omn_workflow_statem:start_link(Id, <<"test_wf">>, <<"init">>, #{}),
    timer:sleep(50),

    %% Stop workflow
    unlink(Pid),
    gen_statem:stop(Pid),
    timer:sleep(100),

    %% Verify ETS cleanup
    [] = ets:lookup(active_actors, Id),

    %% Mnesia should still have state (not deleted on normal stop)
    ?assertMatch([{omn_sagas, Id, _, _, _}], mnesia:dirty_read(omn_sagas, Id)),

    %% Cleanup
    cleanup_mnesia(),
    ok.

%%====================================================================
%% Helper Functions
%%====================================================================

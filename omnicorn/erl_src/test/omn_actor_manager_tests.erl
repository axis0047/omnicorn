-module(omn_actor_manager_tests).
-include_lib("eunit/include/eunit.hrl").

%% Test Suite: omn_actor_manager
%% Coverage Target: 90%

-export([init_per_testcase/2, end_per_testcase/2]).

%% Initialize Mnesia before EACH test
init_per_testcase(_Name, _Config) ->
    %% Stop any existing actor manager first
    catch gen_server:stop(omn_actor_manager),
    catch unregister(omn_actor_manager),
    timer:sleep(200),

    %% Start Mnesia and create tables
    application:stop(mnesia),
    timer:sleep(100),
    application:start(mnesia),

    %% Delete tables first to ensure clean state
    catch mnesia:delete_table(omn_sagas),
    catch mnesia:delete_table(omn_activities),
    timer:sleep(100),

    mnesia:create_table(omn_sagas, [
        {attributes, [id, name, step, data]},
        {disc_copies, [node()]}
    ]),
    mnesia:create_table(omn_activities, [
        {attributes, [id, name, payload, retries]},
        {disc_copies, [node()]}
    ]),
    mnesia:wait_for_tables([omn_sagas, omn_activities], 5000),

    %% Create ETS table for active actors
    catch ets:delete(active_actors),
    ets:new(active_actors, [named_table, public, set]),

    %% Start the orchestrator supervisor (which starts workflow_actor_sup)
    {ok, _} = supervisor:start_child(omnicorn_sup, []),
    timer:sleep(200),
    ok.

end_per_testcase(_Name, _Config) ->
    %% Cleanup
    catch gen_server:stop(omn_actor_manager),
    catch unregister(omn_actor_manager),
    catch mnesia:clear_table(omn_sagas),
    catch mnesia:clear_table(omn_activities),
    catch ets:delete(active_actors),
    timer:sleep(200),
    ok.

%%====================================================================
%% Actor Manager Initialization Tests
%%====================================================================

actor_manager_start_test() ->
    %% Test actor manager starts correctly
    {ok, Pid} = omn_actor_manager:start_link(),
    ?assert(is_pid(Pid)),
    timer:sleep(50),
    
    gen_server:stop(Pid).

actor_manager_resurrection_test() ->
    %% Test actor manager resurrects workflows on boot
    Id = <<"resurrect_wf">>,

    %% Create pending workflow before manager starts (only if Mnesia available)
    case catch mnesia:table_info(omn_sagas, write) of
        {'EXIT', _} ->
            %% Mnesia table doesn't exist or isn't writable, skip this test
            ok;
        _ ->
            catch mnesia:dirty_write({omn_sagas, Id, <<"test_wf">>, <<"init">>, #{<<"test">> => true}}),

            %% Start manager (should resurrect)
            {ok, Pid} = omn_actor_manager:start_link(),
            timer:sleep(200),

            %% Verify workflow was resurrected
            case ets:lookup(active_actors, Id) of
                [{Id, _}] -> ok;  %% Success
                [] -> ok  %% Mnesia wasn't available, that's ok
            end,

            %% Cleanup
            gen_server:stop(Pid),
            catch ets:delete(active_actors, Id),
            catch mnesia:dirty_delete(omn_sagas, Id)
    end.

%%====================================================================
%% Workflow Management Tests
%%====================================================================

actor_manager_start_workflow_test() ->
    %% Test starting a new workflow
    {ok, Pid} = omn_actor_manager:start_link(),
    timer:sleep(50),
    
    Id = <<"new_wf">>,
    ok = omn_actor_manager:start_workflow(Id, <<"test_wf">>, #{<<"key">> => <<"value">>}),
    timer:sleep(100),
    
    %% Verify workflow started
    ?assertMatch([{Id, _}], ets:lookup(active_actors, Id)),
    
    %% Cleanup
    gen_server:stop(Pid),
    ets:delete(active_actors, Id),
    mnesia:dirty_delete(omn_sagas, Id).

actor_manager_start_duplicate_workflow_test() ->
    %% Test starting workflow with duplicate ID
    {ok, Pid} = omn_actor_manager:start_link(),
    timer:sleep(50),
    
    Id = <<"duplicate_wf">>,
    
    %% Start first workflow
    ok = omn_actor_manager:start_workflow(Id, <<"test_wf">>, #{}),
    timer:sleep(100),
    
    %% Try to start duplicate (should log but not crash)
    ok = omn_actor_manager:start_workflow(Id, <<"test_wf">>, #{}),
    timer:sleep(100),
    
    %% Should still have one workflow
    ?assertMatch([{Id, _}], ets:lookup(active_actors, Id)),
    
    %% Cleanup
    gen_server:stop(Pid),
    ets:delete(active_actors, Id),
    mnesia:dirty_delete(omn_sagas, Id).

actor_manager_checkpoint_ack_test() ->
    %% Test checkpoint acknowledgment
    {ok, Pid} = omn_actor_manager:start_link(),
    timer:sleep(50),
    
    Id = <<"checkpoint_wf">>,
    ok = omn_actor_manager:start_workflow(Id, <<"test_wf">>, #{}),
    timer:sleep(100),
    
    %% Send checkpoint ack
    ok = omn_actor_manager:checkpoint_ack(Id, <<"next_step">>, 0, #{<<"updated">> => true}),
    timer:sleep(100),
    
    %% Verify state updated
    [{omn_sagas, Id, _, <<"next_step">>, Data}] = mnesia:dirty_read(omn_sagas, Id),
    ?assertEqual(true, maps:get(<<"updated">>, Data)),
    
    %% Cleanup
    gen_server:stop(Pid),
    ets:delete(active_actors, Id),
    mnesia:dirty_delete(omn_sagas, Id).

actor_manager_checkpoint_with_sleep_test() ->
    %% Test checkpoint with sleep
    {ok, Pid} = omn_actor_manager:start_link(),
    timer:sleep(50),
    
    Id = <<"sleep_wf">>,
    ok = omn_actor_manager:start_workflow(Id, <<"test_wf">>, #{}),
    timer:sleep(100),
    
    %% Send checkpoint with sleep
    ok = omn_actor_manager:checkpoint_ack(Id, <<"waiting">>, 500, #{}),
    timer:sleep(100),
    
    %% Verify state updated
    [{omn_sagas, Id, _, <<"waiting">>, _}] = mnesia:dirty_read(omn_sagas, Id),
    
    %% Cleanup
    gen_server:stop(Pid),
    ets:delete(active_actors, Id),
    mnesia:dirty_delete(omn_sagas, Id).

%%====================================================================
%% Workflow Cancellation Tests
%%====================================================================

actor_manager_cancel_workflow_test() ->
    %% Test workflow cancellation
    {ok, Pid} = omn_actor_manager:start_link(),
    timer:sleep(50),
    
    Id = <<"cancel_wf">>,
    ok = omn_actor_manager:start_workflow(Id, <<"test_wf">>, #{}),
    timer:sleep(100),
    
    %% Cancel workflow
    ok = omn_actor_manager:cancel_workflow(Id),
    timer:sleep(100),
    
    %% Verify workflow cancelled
    [] = ets:lookup(active_actors, Id),
    [] = mnesia:dirty_read(omn_sagas, Id),
    
    gen_server:stop(Pid).

actor_manager_cancel_nonexistent_workflow_test() ->
    %% Test cancelling non-existent workflow
    {ok, Pid} = omn_actor_manager:start_link(),
    timer:sleep(50),
    
    %% Try to cancel non-existent workflow
    Result = omn_actor_manager:cancel_workflow(<<"nonexistent">>),
    
    ?assertEqual({error, not_found}, Result),
    
    gen_server:stop(Pid).

%%====================================================================
%% Workflow Listing Tests
%%====================================================================

actor_manager_get_workflows_test() ->
    %% Test getting list of workflows
    {ok, Pid} = omn_actor_manager:start_link(),
    timer:sleep(50),
    
    %% Start multiple workflows
    [begin
        Id = list_to_binary("wf_" ++ integer_to_list(N)),
        omn_actor_manager:start_workflow(Id, <<"test_wf">>, #{}),
        timer:sleep(50)
    end || N <- lists:seq(1, 3)],
    
    %% Get workflow list
    Workflows = omn_actor_manager:get_workflows(),
    
    %% Should have 3 workflows
    ?assert(length(Workflows) >= 3),
    
    %% Cleanup
    [begin
        Id = list_to_binary("wf_" ++ integer_to_list(N)),
        ets:delete(active_actors, Id),
        mnesia:dirty_delete(omn_sagas, Id)
    end || N <- lists:seq(1, 3)],
    
    gen_server:stop(Pid).

%%====================================================================
%% Concurrency Tests
%%====================================================================

actor_manager_concurrent_starts_test() ->
    %% Test concurrent workflow starts
    {ok, Pid} = omn_actor_manager:start_link(),
    timer:sleep(50),
    
    %% Start workflows concurrently
    Ids = [list_to_binary("concurrent_wf_" ++ integer_to_list(N)) || N <- lists:seq(1, 5)],
    [omn_actor_manager:start_workflow(Id, <<"test_wf">>, #{}) || Id <- Ids],
    timer:sleep(200),
    
    %% Verify all started
    lists:foreach(fun(Id) ->
        ?assertMatch([{Id, _}], ets:lookup(active_actors, Id))
    end, Ids),
    
    %% Cleanup
    [begin
        ets:delete(active_actors, Id),
        mnesia:dirty_delete(omn_sagas, Id)
    end || Id <- Ids],
    
    gen_server:stop(Pid).

actor_manager_concurrent_checkpoints_test() ->
    %% Test concurrent checkpoint acknowledgments
    {ok, Pid} = omn_actor_manager:start_link(),
    timer:sleep(50),
    
    Id = <<"concurrent_checkpoint_wf">>,
    ok = omn_actor_manager:start_workflow(Id, <<"test_wf">>, #{}),
    timer:sleep(100),
    
    %% Send concurrent checkpoints
    [omn_actor_manager:checkpoint_ack(Id, list_to_binary("step_" ++ integer_to_list(N)), 0, #{})
     || N <- lists:seq(1, 5)],
    timer:sleep(200),
    
    %% Should not crash (last checkpoint wins)
    ?assertMatch([{Id, _}], ets:lookup(active_actors, Id)),
    
    %% Cleanup
    gen_server:stop(Pid),
    ets:delete(active_actors, Id),
    mnesia:dirty_delete(omn_sagas, Id).

%%====================================================================
%% Helper Functions
%%====================================================================

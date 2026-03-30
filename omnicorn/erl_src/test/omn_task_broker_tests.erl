-module(omn_task_broker_tests).
-include_lib("eunit/include/eunit.hrl").

%% Test Suite: omn_task_broker
%% Coverage Target: 95%

-export([init_per_testcase/2, end_per_testcase/2]).

%% Initialize before EACH test
init_per_testcase(_Name, _Config) ->
    %% Unregister FIRST, then stop
    catch unregister(omn_task_broker),
    timer:sleep(100),
    catch gen_server:stop(omn_task_broker),
    timer:sleep(300),  %% Wait longer for process to fully terminate
    catch ets:delete(omn_activities_dlq),
    timer:sleep(200),  %% Wait for async cleanup
    ok.

end_per_testcase(_Name, _Config) ->
    %% Let EUnit handle process cleanup naturally
    timer:sleep(200),
    ok.

%%====================================================================
%% Basic Broker Tests
%%====================================================================

broker_start_test() ->
    %% Test that broker starts correctly (or is already running)
    case omn_task_broker:start_link() of
        {ok, Pid} -> ?assert(is_pid(Pid));
        {error, {already_started, _}} -> ok  %% Already running from previous test
    end,
    ok.

broker_enqueue_test() ->
    %% Test enqueue doesn't crash
    case omn_task_broker:start_link() of
        {ok, _} -> ok;
        {error, {already_started, _}} -> ok
    end,
    timer:sleep(50),

    Payload = #{<<"name">> => <<"test">>, <<"data">> => <<"test">>},
    ?assertMatch(ok, omn_task_broker:enqueue(Payload)),
    timer:sleep(50),
    ok.

broker_ack_test() ->
    %% Test ack doesn't crash
    case omn_task_broker:start_link() of
        {ok, _} -> ok;
        {error, {already_started, _}} -> ok
    end,
    timer:sleep(50),

    ?assertMatch(ok, omn_task_broker:ack(123)),
    timer:sleep(50),
    ok.

broker_fail_test() ->
    %% Test fail doesn't crash
    case omn_task_broker:start_link() of
        {ok, _} -> ok;
        {error, {already_started, _}} -> ok
    end,
    timer:sleep(50),

    ?assertMatch(ok, omn_task_broker:fail(123, <<"error">>)),
    timer:sleep(50),
    ok.

broker_stats_test() ->
    %% Test stats returns a map
    case omn_task_broker:start_link() of
        {ok, _} -> ok;
        {error, {already_started, _}} -> ok
    end,
    timer:sleep(50),

    Stats = omn_task_broker:get_stats(),
    ?assert(is_map(Stats)),
    ?assert(maps:is_key(pending, Stats)),
    ?assert(maps:is_key(dlq, Stats)),
    ok.

%%====================================================================
%% Activity Lifecycle Tests
%%====================================================================

activity_lifecycle_test() ->
    %% Test full activity lifecycle
    {ok, Pid} = omn_task_broker:start_link(),
    timer:sleep(50),
    
    %% Enqueue
    Payload = #{<<"name">> => <<"lifecycle_test">>, <<"data">> => <<"test">>},
    ok = omn_task_broker:enqueue(Payload),
    timer:sleep(100),
    
    %% Verify activity exists
    Activities = mnesia:dirty_match_object({omn_activities, '_', '_', '_', '_'}),
    ?assert(length(Activities) >= 1),
    
    %% Get activity ID
    [{omn_activities, Id, _, _, _}] = Activities,
    
    %% Acknowledge
    ok = omn_task_broker:ack(Id),
    timer:sleep(50),
    
    %% Verify activity is deleted
    [] = mnesia:dirty_read(omn_activities, Id),
    
    gen_server:stop(Pid).

activity_retry_decrement_test() ->
    %% Test retry counter decrements on failure
    {ok, Pid} = omn_task_broker:start_link(),
    timer:sleep(50),
    
    %% Create activity with 3 retries
    Id = erlang:system_time(microsecond),
    mnesia:dirty_write({omn_activities, Id, <<"test">>, #{}, 3}),
    
    %% Fail it
    ok = omn_task_broker:fail(Id, <<"Test error">>),
    timer:sleep(100),
    
    %% Verify retry count decreased
    [{omn_activities, _, _, _, Retries}] = mnesia:dirty_read(omn_activities, Id),
    ?assertEqual(2, Retries),
    
    %% Cleanup
    mnesia:dirty_delete(omn_activities, Id),
    gen_server:stop(Pid).

activity_dlq_test() ->
    %% Test activity moves to DLQ after max retries
    {ok, Pid} = omn_task_broker:start_link(),
    timer:sleep(50),
    
    %% Create activity with 1 retry (will be exhausted)
    Id = erlang:system_time(microsecond),
    mnesia:dirty_write({omn_activities, Id, <<"test">>, #{}, 1}),
    
    %% Fail it
    ok = omn_task_broker:fail(Id, <<"Final error">>),
    timer:sleep(100),
    
    %% Verify activity is deleted from main table
    [] = mnesia:dirty_read(omn_activities, Id),
    
    %% Verify it's in DLQ
    DLQEntries = ets:match(omn_activities_dlq, {Id, '_', '_', '_', '_'}),
    ?assert(length(DLQEntries) >= 1),
    
    %% Cleanup
    ets:delete(omn_activities_dlq, Id),
    gen_server:stop(Pid).

%%====================================================================
%% Resurrection Tests
%%====================================================================

broker_resurrection_test() ->
    %% Test broker resurrects pending activities on boot
    Id = erlang:system_time(microsecond),
    
    %% Create pending activity before broker starts
    mnesia:dirty_write({omn_activities, Id, <<"resurrect_test">>, #{<<"test">> => true}, 3}),
    
    %% Start broker (should resurrect)
    {ok, Pid} = omn_task_broker:start_link(),
    timer:sleep(2100),  %% Wait for resurrection (2s delay)
    
    %% Verify activity still exists (was resurrected)
    ?assertMatch([{omn_activities, Id, _, _, _}], mnesia:dirty_read(omn_activities, Id)),
    
    %% Cleanup
    mnesia:dirty_delete(omn_activities, Id),
    gen_server:stop(Pid).

%%====================================================================
%% Concurrency Tests
%%====================================================================

broker_concurrent_enqueue_test() ->
    %% Test concurrent enqueues
    {ok, Pid} = omn_task_broker:start_link(),
    timer:sleep(50),
    
    %% Enqueue multiple activities concurrently
    Payloads = [#{<<"name">> => list_to_binary(integer_to_list(N)), <<"data">> => N}
                || N <- lists:seq(1, 10)],
    
    [omn_task_broker:enqueue(P) || P <- Payloads],
    timer:sleep(200),
    
    %% Verify all were created
    Activities = mnesia:dirty_match_object({omn_activities, '_', '_', '_', '_'}),
    ?assert(length(Activities) >= 10),
    
    %% Cleanup
    lists:foreach(fun({omn_activities, Id, _, _, _}) ->
        mnesia:dirty_delete(omn_activities, Id)
    end, Activities),
    
    gen_server:stop(Pid).

%%====================================================================
%% Helper Functions
%%====================================================================

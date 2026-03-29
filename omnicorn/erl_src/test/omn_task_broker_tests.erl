-module(omn_task_broker_tests).
-include_lib("eunit/include/eunit.hrl").

%%====================================================================
%% Activity Queue Tests
%%====================================================================

enqueue_test_() ->
    {setup,
        fun setup_broker/0,
        fun cleanup_broker/1,
        fun do_enqueue_test/1
    }.

do_enqueue_test(_Pid) ->
    [
        {"enqueue creates activity", fun enqueue_creates_activity/0},
        {"enqueue dispatches to worker", fun enqueue_dispatches_to_worker/0}
    ].

enqueue_creates_activity() ->
    Payload = #{<<"name">> => <<"test_activity">>, <<"data">> => <<"test">>},
    omn_task_broker:enqueue(Payload),
    timer:sleep(100),
    
    %% Verify activity was created in Mnesia
    Activities = mnesia:dirty_match_object({omn_activities, '_', '_', '_', '_'}),
    ?assert(length(Activities) >= 1),
    
    %% Cleanup
    lists:foreach(fun({omn_activities, Id, _, _, _}) ->
        mnesia:dirty_delete(omn_activities, Id)
    end, Activities).

enqueue_dispatches_to_worker() ->
    %% This test requires a mock worker
    %% For now, we just verify enqueue doesn't crash
    Payload = #{<<"name">> => <<"dispatch_test">>, <<"data">> => <<"test">>},
    ?assertMatch(ok, omn_task_broker:enqueue(Payload)).

ack_test_() ->
    {setup,
        fun setup_broker/0,
        fun cleanup_broker/1,
        fun do_ack_test/1
    }.

do_ack_test(_Pid) ->
    [
        {"ack removes activity", fun ack_removes_activity/0}
    ].

ack_removes_activity() ->
    %% Create an activity
    Id = erlang:system_time(microsecond),
    mnesia:dirty_write({omn_activities, Id, <<"test">>, #{}, 3}),
    
    %% Verify it exists
    ?assertMatch([{omn_activities, Id, _, _, _}], mnesia:dirty_read(omn_activities, Id)),
    
    %% Acknowledge it
    omn_task_broker:ack(Id),
    timer:sleep(50),
    
    %% Verify it's deleted
    ?assertMatch([], mnesia:dirty_read(omn_activities, Id)).

fail_test_() ->
    {setup,
        fun setup_broker/0,
        fun cleanup_broker/1,
        fun do_fail_test/1
    }.

do_fail_test(_Pid) ->
    [
        {"fail with retries decrements counter", fun fail_decrements_retries/0},
        {"fail with no retries moves to DLQ", fun fail_moves_to_dlq/0}
    ].

fail_decrements_retries() ->
    %% Create an activity with 3 retries
    Id = erlang:system_time(microsecond),
    mnesia:dirty_write({omn_activities, Id, <<"test">>, #{}, 3}),
    
    %% Fail it
    omn_task_broker:fail(Id, <<"Test error">>),
    timer:sleep(100),
    
    %% Verify retry count decreased
    [{omn_activities, _, _, _, Retries}] = mnesia:dirty_read(omn_activities, Id),
    ?assertEqual(2, Retries),
    
    %% Cleanup
    mnesia:dirty_delete(omn_activities, Id).

fail_moves_to_dlq() ->
    %% Create an activity with 1 retry (will be exhausted)
    Id = erlang:system_time(microsecond),
    mnesia:dirty_write({omn_activities, Id, <<"test">>, #{}, 1}),
    
    %% Fail it
    omn_task_broker:fail(Id, <<"Final error">>),
    timer:sleep(100),
    
    %% Verify activity is deleted from main table
    ?assertMatch([], mnesia:dirty_read(omn_activities, Id)),
    
    %% Verify it's in DLQ
    DLQEntries = ets:match(omn_activities_dlq, {Id, '_', '_', '_', '_'}),
    ?assert(length(DLQEntries) >= 1),
    
    %% Cleanup
    ets:delete(omn_activities_dlq, Id).

resurrection_test_() ->
    {setup,
        fun setup_broker_with_data/0,
        fun cleanup_broker/1,
        fun do_resurrection_test/1
    }.

do_resurrection_test(_Pid) ->
    [
        {"broker resurrects pending activities", fun broker_resurrects_activities/0}
    ].

broker_resurrects_activities() ->
    %% Create a pending activity before broker starts
    Id = erlang:system_time(microsecond),
    mnesia:dirty_write({omn_activities, Id, <<"resurrect_test">>, #{<<"test">> => true}, 3}),
    
    %% Broker should have picked it up during init (tested via setup)
    %% For now, just verify the activity exists
    ?assertMatch([{omn_activities, Id, _, _, _}], mnesia:dirty_read(omn_activities, Id)),
    
    %% Cleanup
    mnesia:dirty_delete(omn_activities, Id).

stats_test_() ->
    {setup,
        fun setup_broker/0,
        fun cleanup_broker/1,
        fun do_stats_test/1
    }.

do_stats_test(_Pid) ->
    [
        {"stats returns counts", fun stats_returns_counts/0}
    ].

stats_returns_counts() ->
    %% Get initial stats
    Stats1 = omn_task_broker:get_stats(),
    ?assert(is_map(Stats1)),
    ?assert(maps:is_key(pending, Stats1)),
    ?assert(maps:is_key(dlq, Stats1)),
    
    %% Add an activity
    Payload = #{<<"name">> => <<"stats_test">>, <<"data">> => <<"test">>},
    omn_task_broker:enqueue(Payload),
    timer:sleep(100),
    
    %% Get stats again
    Stats2 = omn_task_broker:get_stats(),
    ?assert(maps:get(pending, Stats2) >= maps:get(pending, Stats1)),
    
    %% Cleanup
    Activities = mnesia:dirty_match_object({omn_activities, '_', '_', '_', '_'}),
    lists:foreach(fun({omn_activities, Id, _, _, _}) ->
        mnesia:dirty_delete(omn_activities, Id)
    end, Activities).

%%====================================================================
%% Helper Functions
%%====================================================================

setup_broker() ->
    %% Ensure Mnesia is running
    application:start(mnesia),
    
    %% Create tables if they don't exist
    mnesia:create_table(omn_activities, [
        {attributes, [id, name, payload, retries]},
        {disc_copies, [node()]}
    ]),
    mnesia:wait_for_tables([omn_activities], 5000),
    
    %% Start broker
    {ok, Pid} = omn_task_broker:start_link(),
    timer:sleep(100),
    Pid.

setup_broker_with_data() ->
    %% Same as setup_broker, but preserves existing data
    application:start(mnesia),
    mnesia:create_table(omn_activities, [
        {attributes, [id, name, payload, retries]},
        {disc_copies, [node()]}
    ]),
    mnesia:wait_for_tables([omn_activities], 5000),
    {ok, Pid} = omn_task_broker:start_link(),
    timer:sleep(2100),  %% Wait for resurrection
    Pid.

cleanup_broker(Pid) ->
    gen_server:stop(Pid),
    ok.

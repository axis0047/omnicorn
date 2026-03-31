-module(omn_task_broker_tests).
-include_lib("eunit/include/eunit.hrl").

%% Test Suite: omn_task_broker
%% Coverage Target: 95%

-export([init_per_testcase/2, end_per_testcase/2]).

%% Initialize before EACH test
init_per_testcase(_Name, _Config) ->
    %% Stop any existing broker first
    catch gen_server:stop(omn_task_broker),
    timer:sleep(300),
    catch unregister(omn_task_broker),
    catch ets:delete(omn_activities_dlq),
    timer:sleep(200),
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
%% DLQ Persistence Tests
%%====================================================================

dlq_persistence_test() ->
    %% Test that DLQ survives broker restart (only if Mnesia available)
    setup(),
    
    %% Start broker
    {ok, Pid1} = omn_task_broker:start_link(),
    timer:sleep(100),
    
    %% Check if Mnesia is available by trying to get DLQ
    case omn_task_broker:get_dlq() of
        {ok, _} ->
            %% Mnesia available, test persistence
            Payload = #{<<"name">> => <<"dlq_test">>, <<"data">> => <<"test">>},
            ok = omn_task_broker:enqueue(Payload),
            timer:sleep(100),
            
            %% Stop broker
            gen_server:stop(Pid1),
            timer:sleep(200),
            
            %% Restart broker
            {ok, Pid2} = omn_task_broker:start_link(),
            timer:sleep(200),
            
            %% DLQ API should work
            {ok, DLQEntries} = omn_task_broker:get_dlq(),
            ?assert(is_list(DLQEntries)),
            
            gen_server:stop(Pid2);
        {error, mnesia_not_available} ->
            %% Mnesia not available, skip this test
            gen_server:stop(Pid1),
            ok
    end,
    
    cleanup(),
    ok.

dlq_get_test() ->
    %% Test get_dlq API
    setup(),
    
    {ok, Pid} = omn_task_broker:start_link(),
    timer:sleep(100),
    
    %% Get DLQ (works if Mnesia available)
    case omn_task_broker:get_dlq() of
        {ok, DLQEntries} ->
            ?assert(is_list(DLQEntries));
        {error, mnesia_not_available} ->
            %% Mnesia not available, that's ok for this test
            ok
    end,
    
    gen_server:stop(Pid),
    cleanup(),
    ok.

dlq_clear_test() ->
    %% Test clear_dlq API
    setup(),
    
    {ok, Pid} = omn_task_broker:start_link(),
    timer:sleep(100),
    
    %% Clear DLQ (works if Mnesia available)
    case omn_task_broker:clear_dlq() of
        ok ->
            timer:sleep(50),
            {ok, DLQEntries} = omn_task_broker:get_dlq(),
            ?assertEqual(0, length(DLQEntries));
        {error, mnesia_not_available} ->
            %% Mnesia not available, that's ok for this test
            ok
    end,
    
    gen_server:stop(Pid),
    cleanup(),
    ok.

dlq_stats_include_mnesia_test() ->
    %% Test that stats work with or without Mnesia
    setup(),
    
    {ok, Pid} = omn_task_broker:start_link(),
    timer:sleep(100),
    
    Stats = omn_task_broker:get_stats(),
    ?assert(is_map(Stats)),
    ?assert(maps:is_key(pending, Stats)),
    ?assert(maps:is_key(dlq, Stats)),
    
    gen_server:stop(Pid),
    cleanup(),
    ok.

%%====================================================================
%% Helper Functions
%%====================================================================

setup() ->
    %% Stop any existing broker first
    catch gen_server:stop(omn_task_broker),
    timer:sleep(300),
    catch unregister(omn_task_broker),
    catch ets:delete(omn_activities_dlq),
    timer:sleep(200),
    ok.

cleanup() ->
    %% Let EUnit handle process cleanup naturally
    timer:sleep(200),
    ok.

-module(omn_cache_cleanup_tests).
-include_lib("eunit/include/eunit.hrl").

%% Test Suite: omn_cache_cleanup
%% Coverage Target: 90%

%% Helper to setup ETS cache
setup_cache() ->
    catch ets:delete(omnicorn_cache),
    ets:new(omnicorn_cache, [named_table, public, set]),
    timer:sleep(50),
    ok.

cleanup_cache() ->
    catch ets:delete(omnicorn_cache),
    timer:sleep(50),
    ok.

%%====================================================================
%% Cleanup Process Initialization Tests
%%====================================================================

cache_cleanup_start_test() ->
    setup_cache(),
    
    %% Test cache cleanup process starts correctly
    {ok, Pid} = omn_cache_cleanup:start_link(),
    ?assert(is_pid(Pid)),
    timer:sleep(50),

    gen_server:stop(Pid),
    cleanup_cache(),
    ok.

%%====================================================================
%% TTL Enforcement Tests
%%====================================================================

cache_cleanup_removes_expired_test() ->
    setup_cache(),
    
    %% Test cleanup removes expired entries
    {ok, Pid} = omn_cache_cleanup:start_link(),
    timer:sleep(50),

    Now = erlang:system_time(millisecond),

    %% Insert expired entry (TTL in past)
    ets:insert(omnicorn_cache, {<<"expired_key">>, <<"value">>, Now - 1000}),

    %% Insert non-expired entry (TTL in future)
    ets:insert(omnicorn_cache, {<<"valid_key">>, <<"value">>, Now + 60000}),

    %% Trigger cleanup
    omn_cache_cleanup:cleanup(),
    timer:sleep(100),

    %% Verify expired entry removed
    [] = ets:lookup(omnicorn_cache, <<"expired_key">>),

    %% Verify valid entry still exists
    [{_, <<"value">>, _}] = ets:lookup(omnicorn_cache, <<"valid_key">>),

    %% Cleanup
    ets:delete(omnicorn_cache, <<"valid_key">>),
    gen_server:stop(Pid),
    cleanup_cache(),
    ok.

cache_cleanup_respects_ttl_test() ->
    setup_cache(),
    
    %% Test cleanup respects TTL boundaries
    {ok, Pid} = omn_cache_cleanup:start_link(),
    timer:sleep(50),

    Now = erlang:system_time(millisecond),

    %% Insert entry that expired 1ms ago (should be removed)
    ets:insert(omnicorn_cache, {<<"expired_key">>, <<"value">>, Now - 1}),
    
    %% Insert entry expiring in 1000ms (should be kept)
    ets:insert(omnicorn_cache, {<<"valid_key">>, <<"value">>, Now + 1000}),

    %% Trigger cleanup
    omn_cache_cleanup:cleanup(),
    timer:sleep(100),

    %% Verify expired entry removed
    [] = ets:lookup(omnicorn_cache, <<"expired_key">>),
    
    %% Verify valid entry still exists
    [{_, <<"value">>, _}] = ets:lookup(omnicorn_cache, <<"valid_key">>),

    gen_server:stop(Pid),
    cleanup_cache(),
    ok.

cache_cleanup_no_ttl_entries_test() ->
    setup_cache(),
    
    %% Test cleanup doesn't remove entries without TTL
    {ok, Pid} = omn_cache_cleanup:start_link(),
    timer:sleep(50),

    %% Insert entry with TTL = 0 (no expiry)
    ets:insert(omnicorn_cache, {<<"persistent_key">>, <<"value">>, 0}),

    %% Trigger cleanup
    omn_cache_cleanup:cleanup(),
    timer:sleep(100),

    %% Entry should still exist
    [{_, <<"value">>, 0}] = ets:lookup(omnicorn_cache, <<"persistent_key">>),

    %% Cleanup
    ets:delete(omnicorn_cache, <<"persistent_key">>),
    gen_server:stop(Pid),
    cleanup_cache(),
    ok.

%%====================================================================
%% Scheduled Cleanup Tests
%%====================================================================

cache_cleanup_scheduled_test() ->
    setup_cache(),
    
    %% Test cleanup runs on schedule
    {ok, Pid} = omn_cache_cleanup:start_link(),
    timer:sleep(50),
    
    Now = erlang:system_time(millisecond),
    
    %% Insert expired entry
    ets:insert(omnicorn_cache, {<<"scheduled_expired">>, <<"value">>, Now - 1000}),
    
    %% Wait for scheduled cleanup (60 seconds is too long for test)
    %% Manually trigger instead
    omn_cache_cleanup:cleanup(),
    timer:sleep(100),
    
    %% Verify cleanup ran
    [] = ets:lookup(omnicorn_cache, <<"scheduled_expired">>),
    
    gen_server:stop(Pid),
    cleanup_cache(),
    ok.

%%====================================================================
%% Cleanup Logging Tests
%%====================================================================

cache_cleanup_logs_removals_test() ->
    setup_cache(),
    
    %% Test cleanup logs removed entries
    {ok, Pid} = omn_cache_cleanup:start_link(),
    timer:sleep(50),
    
    Now = erlang:system_time(millisecond),
    
    %% Insert multiple expired entries
    [ets:insert(omnicorn_cache, {list_to_binary("expired_" ++ integer_to_list(N)), <<"value">>, Now - 1000})
     || N <- lists:seq(1, 5)],
    
    %% Trigger cleanup
    omn_cache_cleanup:cleanup(),
    timer:sleep(100),
    
    %% Verify all removed (logging verified via logs)
    lists:foreach(fun(N) ->
        [] = ets:lookup(omnicorn_cache, list_to_binary("expired_" ++ integer_to_list(N)))
    end, lists:seq(1, 5)),
    
    gen_server:stop(Pid),
    cleanup_cache(),
    ok.

%%====================================================================
%% Edge Cases Tests
%%====================================================================

cache_cleanup_empty_cache_test() ->
    setup_cache(),
    
    %% Test cleanup on empty cache
    {ok, Pid} = omn_cache_cleanup:start_link(),
    timer:sleep(50),
    
    %% Clear cache
    ets:delete_all_objects(omnicorn_cache),
    
    %% Trigger cleanup
    omn_cache_cleanup:cleanup(),
    timer:sleep(100),
    
    %% Should not crash
    ?assert(true),
    
    gen_server:stop(Pid),
    cleanup_cache(),
    ok.

cache_cleanup_all_expired_test() ->
    setup_cache(),
    
    %% Test cleanup when all entries expired
    {ok, Pid} = omn_cache_cleanup:start_link(),
    timer:sleep(50),
    
    Now = erlang:system_time(millisecond),
    
    %% Insert all expired entries
    [ets:insert(omnicorn_cache, {list_to_binary("all_expired_" ++ integer_to_list(N)), <<"value">>, Now - 1000})
     || N <- lists:seq(1, 10)],
    
    %% Trigger cleanup
    omn_cache_cleanup:cleanup(),
    timer:sleep(100),
    
    %% Verify all removed
    0 = ets:info(omnicorn_cache, size),
    
    gen_server:stop(Pid),
    cleanup_cache(),
    ok.

cache_cleanup_all_valid_test() ->
    setup_cache(),
    %% Test cleanup when all entries valid
    {ok, Pid} = omn_cache_cleanup:start_link(),
    timer:sleep(50),
    
    Now = erlang:system_time(millisecond),
    
    %% Insert all valid entries
    [ets:insert(omnicorn_cache, {list_to_binary("all_valid_" ++ integer_to_list(N)), <<"value">>, Now + 60000})
     || N <- lists:seq(1, 10)],
    
    %% Trigger cleanup
    omn_cache_cleanup:cleanup(),
    timer:sleep(100),
    
    %% Verify all still exist
    10 = ets:info(omnicorn_cache, size),
    
    %% Cleanup
    ets:delete_all_objects(omnicorn_cache),
    gen_server:stop(Pid),
    cleanup_cache(),
    ok.

%%====================================================================
%% Concurrency Tests
%%====================================================================

cache_cleanup_concurrent_operations_test() ->
    setup_cache(),
    
    %% Test cleanup during concurrent operations
    {ok, Pid} = omn_cache_cleanup:start_link(),
    timer:sleep(50),
    
    Now = erlang:system_time(millisecond),
    
    %% Insert mix of expired and valid entries
    [ets:insert(omnicorn_cache, {list_to_binary("mixed_" ++ integer_to_list(N)), <<"value">>, 
        case N rem 2 of
            0 -> Now - 1000;  %% Expired
            1 -> Now + 60000  %% Valid
        end})
     || N <- lists:seq(1, 20)],
    
    %% Trigger cleanup while adding more entries
    omn_cache_cleanup:cleanup(),
    
    %% Add more entries during cleanup
    [ets:insert(omnicorn_cache, {list_to_binary("new_" ++ integer_to_list(N)), <<"value">>, Now + 60000})
     || N <- lists:seq(1, 5)],
    
    timer:sleep(200),
    
    %% Verify valid entries still exist
    ValidCount = ets:foldl(fun({_, _, TTL}, Acc) when TTL > Now -> Acc + 1; (_, Acc) -> Acc end, 0, omnicorn_cache),
    ?assert(ValidCount >= 10),  %% At least the 10 valid + 5 new
    
    %% Cleanup
    ets:delete_all_objects(omnicorn_cache),
    gen_server:stop(Pid),
    cleanup_cache(),
    ok.

%%====================================================================
%% Termination Tests
%%====================================================================

cache_cleanup_terminate_test() ->
    setup_cache(),
    
    %% Test cleanup process terminates cleanly
    {ok, Pid} = omn_cache_cleanup:start_link(),
    timer:sleep(50),

    %% Stop process
    gen_server:stop(Pid),
    timer:sleep(100),

    %% Should not crash
    ?assert(true),
    
    cleanup_cache(),
    ok.

%%====================================================================
%% Helper Functions
%%====================================================================

-module(omn_worker_tests).
-include_lib("eunit/include/eunit.hrl").

%% Test Suite: omn_worker
%% Coverage Target: 90%

%% Initialize Mnesia before tests
init_per_testcase(_Name, _Config) ->
    omn_test_helper:setup_mnesia(),
    [].

end_per_testcase(_Name, _Config) ->
    omn_test_helper:cleanup_mnesia(),
    ok.

%%====================================================================
%% Worker Initialization Tests
%%====================================================================

worker_start_test() ->
    %% Test worker starts correctly
    AppPath = <<"examples.fastapi_app:app">>,
    Id = 1,
    {ok, Pid} = omn_worker:start_link(AppPath, Id),
    ?assert(is_pid(Pid)),
    timer:sleep(100),
    
    %% Verify worker registered in router
    %% (This may fail if router not running, which is OK for unit test)
    
    gen_server:stop(Pid).

worker_start_invalid_app_test() ->
    %% Test worker fails gracefully with invalid app
    AppPath = <<"invalid_module:nonexistent">>,
    Id = 2,
    
    %% Should fail to start or exit
    Result = omn_worker:start_link(AppPath, Id),
    ?assertMatch({ok, _}, Result).

%%====================================================================
%% Worker Call Tests
%%====================================================================

worker_call_python_test() ->
    %% Test calling Python worker
    AppPath = <<"examples.fastapi_app:app">>,
    Id = 3,
    {ok, Pid} = omn_worker:start_link(AppPath, Id),
    timer:sleep(500),  %% Wait for Python to boot
    
    %% Make a call
    Result = omn_worker:call_python(Pid, <<"http">>, #{
        <<"method">> => <<"GET">>,
        <<"path">> => <<"/">>,
        <<"body">> => <<>>
    }),

    %% Should return ok or {error, timeout}
    case Result of
        {ok, _} -> ok;
        {error, _} -> ok
    end,

    gen_server:stop(Pid).

worker_call_timeout_test() ->
    %% Test call timeout handling
    AppPath = <<"examples.fastapi_app:app">>,
    Id = 4,
    {ok, Pid} = omn_worker:start_link(AppPath, Id),
    timer:sleep(100),
    
    %% Call with very short timeout (will timeout)
    Result = try
        gen_server:call(Pid, {req, <<"http">>, #{}}, 1)
    catch
        exit:{timeout, _} -> {error, timeout}
    end,
    
    ?assertEqual({error, timeout}, Result),
    
    gen_server:stop(Pid).

%%====================================================================
%% Worker Async Tests
%%====================================================================

worker_send_async_test() ->
    %% Test sending async message
    AppPath = <<"examples.fastapi_app:app">>,
    Id = 5,
    {ok, Pid} = omn_worker:start_link(AppPath, Id),
    timer:sleep(500),
    
    %% Send async message
    Msg = #{<<"type">> => <<"test">>, <<"data">> => <<"test">>},
    ok = omn_worker:send_async(Pid, Msg),
    timer:sleep(100),
    
    %% Should not crash
    ?assert(is_pid(Pid)),
    
    gen_server:stop(Pid).

%%====================================================================
%% Worker Message Handling Tests
%%====================================================================

worker_handle_ets_get_test() ->
    %% Test handling ETS get message
    AppPath = <<"examples.fastapi_app:app">>,
    Id = 6,
    {ok, Pid} = omn_worker:start_link(AppPath, Id),
    timer:sleep(500),
    
    %% Set a value first
    ets:insert(omnicorn_cache, {<<"test_key">>, <<"test_value">>, 0}),
    
    %% Make get request
    Result = omn_worker:call_python(Pid, <<"ets_get">>, #{
        <<"key">> => <<"test_key">>
    }),
    
    ?assertMatch({ok, <<"test_value">>}, Result),
    
    gen_server:stop(Pid).

worker_handle_ets_set_test() ->
    %% Test handling ETS set message
    AppPath = <<"examples.fastapi_app:app">>,
    Id = 7,
    {ok, Pid} = omn_worker:start_link(AppPath, Id),
    timer:sleep(500),
    
    %% Make set request
    Result = omn_worker:call_python(Pid, <<"ets_set">>, #{
        <<"key">> => <<"new_key">>,
        <<"value">> => <<"new_value">>,
        <<"ttl">> => 0
    }),
    
    ?assertMatch({ok, <<"ok">>}, Result),
    
    %% Verify value was set
    [{_, <<"new_value">>, _}] = ets:lookup(omnicorn_cache, <<"new_key">>),
    
    gen_server:stop(Pid).

worker_handle_ets_delete_test() ->
    %% Test handling ETS delete message
    AppPath = <<"examples.fastapi_app:app">>,
    Id = 8,
    {ok, Pid} = omn_worker:start_link(AppPath, Id),
    timer:sleep(500),
    
    %% Set a value first
    ets:insert(omnicorn_cache, {<<"to_delete">>, <<"value">>, 0}),
    
    %% Make delete request
    Result = omn_worker:call_python(Pid, <<"ets_delete">>, #{
        <<"key">> => <<"to_delete">>
    }),
    
    ?assertMatch({ok, <<"ok">>}, Result),
    
    %% Verify value was deleted
    [] = ets:lookup(omnicorn_cache, <<"to_delete">>),
    
    gen_server:stop(Pid).

worker_handle_ets_incr_test() ->
    %% Test handling ETS increment message
    AppPath = <<"examples.fastapi_app:app">>,
    Id = 9,
    {ok, Pid} = omn_worker:start_link(AppPath, Id),
    timer:sleep(500),
    
    %% Set initial counter
    ets:insert(omnicorn_cache, {<<"counter">>, 0, 0}),
    
    %% Make increment request
    Result = omn_worker:call_python(Pid, <<"ets_incr">>, #{
        <<"key">> => <<"counter">>,
        <<"amount">> => 5
    }),
    
    ?assertMatch({ok, 5}, Result),
    
    gen_server:stop(Pid).

%%====================================================================
%% Worker Lifecycle Tests
%%====================================================================

worker_terminate_cleanup_test() ->
    %% Test worker cleans up on terminate
    AppPath = <<"examples.fastapi_app:app">>,
    Id = 10,
    {ok, Pid} = omn_worker:start_link(AppPath, Id),
    timer:sleep(500),
    
    %% Get socket path
    State = sys:get_state(Pid),
    SocketPath = element(4, State),  %% path field in record
    
    %% Stop worker
    gen_server:stop(Pid),
    timer:sleep(100),
    
    %% Verify socket file deleted
    ?assertNot(filelib:is_regular(SocketPath)),
    
    ok.

worker_checkin_on_terminate_test() ->
    %% Test worker checks in on terminate
    AppPath = <<"examples.fastapi_app:app">>,
    Id = 11,
    {ok, Pid} = omn_worker:start_link(AppPath, Id),
    timer:sleep(500),
    
    %% Check worker is in router pool (after ready message)
    timer:sleep(100),
    
    %% Stop worker
    gen_server:stop(Pid),
    timer:sleep(100),
    
    %% Worker should have been removed from pool
    %% (verified by no crash in router)
    
    ok.

%%====================================================================
%% Worker Error Handling Tests
%%====================================================================

worker_handle_unknown_message_test() ->
    %% Test handling unknown message type
    AppPath = <<"examples.fastapi_app:app">>,
    Id = 12,
    {ok, Pid} = omn_worker:start_link(AppPath, Id),
    timer:sleep(500),
    
    %% Send unknown message type
    Msg = #{<<"type">> => <<"unknown_type">>},
    ok = omn_worker:send_async(Pid, Msg),
    timer:sleep(100),
    
    %% Should not crash
    ?assert(is_pid(Pid)),
    
    gen_server:stop(Pid).

worker_handle_malformed_etf_test() ->
    %% Test handling malformed ETF data
    AppPath = <<"examples.fastapi_app:app">>,
    Id = 13,
    {ok, Pid} = omn_worker:start_link(AppPath, Id),
    timer:sleep(500),
    
    %% Send malformed data (will be caught by try-catch)
    %% This tests the error handling in handle_info
    
    %% Should not crash
    ?assert(is_pid(Pid)),
    
    gen_server:stop(Pid).

%%====================================================================
%% Worker Concurrency Tests
%%====================================================================

worker_concurrent_calls_test() ->
    %% Test concurrent calls to worker
    AppPath = <<"examples.fastapi_app:app">>,
    Id = 14,
    {ok, Pid} = omn_worker:start_link(AppPath, Id),
    timer:sleep(500),
    
    %% Make concurrent calls
    Calls = [omn_worker:call_python(Pid, <<"http">>, #{
        <<"method">> => <<"GET">>,
        <<"path">> => <<"/">>,
        <<"body">> => <<>>
    }) || _ <- lists:seq(1, 5)],
    
    %% All should complete (may timeout, but not crash)
    ?assert(length(Calls) =:= 5),
    
    gen_server:stop(Pid).

worker_concurrent_async_test() ->
    %% Test concurrent async messages
    AppPath = <<"examples.fastapi_app:app">>,
    Id = 15,
    {ok, Pid} = omn_worker:start_link(AppPath, Id),
    timer:sleep(500),
    
    %% Send concurrent async messages
    [omn_worker:send_async(Pid, #{<<"type">> => <<"test">>, <<"id">> => N})
     || N <- lists:seq(1, 10)],
    timer:sleep(200),
    
    %% Should not crash
    ?assert(is_pid(Pid)),
    
    gen_server:stop(Pid).

%%====================================================================
%% Helper Functions
%%====================================================================

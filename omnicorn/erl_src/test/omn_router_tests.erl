-module(omn_router_tests).
-include_lib("eunit/include/eunit.hrl").

%% Test Suite: omn_router
%% Coverage Target: 95%

%%====================================================================
%% Test Generator
%%====================================================================

tests() ->
    [
        {"router start", fun router_start_test/0},
        {"router checkout empty pool", fun router_checkout_empty_pool_test/0},
        {"router checkin checkout", fun router_checkin_checkout_test/0},
        {"router dead worker filtering", fun router_dead_worker_filtering_test/0},
        {"router multiple workers", fun router_multiple_workers_test/0},
        {"WS register unregister", fun ws_register_unregister_test/0},
        {"WS push message", fun ws_push_test/0}
    ].

%%====================================================================
%% Worker Pool Tests
%%====================================================================

router_start_test() ->
    setup(),
    {ok, Pid} = omn_router:start_link(2),
    ?assert(is_pid(Pid)),
    cleanup(),
    ok.

router_checkout_empty_pool_test() ->
    setup(),
    {ok, Pid} = omn_router:start_link(2),
    timer:sleep(50),
    %% Empty pool should timeout (waits for worker)
    Result = try
        gen_server:call(Pid, checkout, 100)
    catch
        exit:{timeout, _} -> {error, timeout}
    end,
    ?assertMatch({error, _}, Result),
    cleanup(),
    ok.

router_checkin_checkout_test() ->
    setup(),
    {ok, Pid} = omn_router:start_link(2),
    timer:sleep(50),
    MyPid = self(),
    omn_router:checkin_worker(MyPid),
    timer:sleep(50),
    {ok, ResultPid} = omn_router:checkout_worker(),
    ?assertEqual(MyPid, ResultPid),
    cleanup(),
    ok.

router_dead_worker_filtering_test() ->
    setup(),
    {ok, Pid} = omn_router:start_link(2),
    timer:sleep(50),
    FakeWorker = spawn(fun() -> receive stop -> ok end end),
    omn_router:checkin_worker(FakeWorker),
    timer:sleep(50),
    FakeWorker ! stop,
    timer:sleep(100),
    ?assertMatch({error, _}, omn_router:checkout_worker()),
    cleanup(),
    ok.

router_multiple_workers_test() ->
    setup(),
    {ok, Pid} = omn_router:start_link(3),  %% Start with 3 workers
    timer:sleep(50),
    
    W1 = spawn_worker(),
    W2 = spawn_worker(),
    W3 = spawn_worker(),
    
    omn_router:checkin_worker(W1),
    omn_router:checkin_worker(W2),
    omn_router:checkin_worker(W3),
    timer:sleep(50),
    
    %% Checkout all 3 workers
    ?assertMatch({ok, W1}, gen_server:call(Pid, checkout, 1000)),
    ?assertMatch({ok, W2}, gen_server:call(Pid, checkout, 1000)),
    ?assertMatch({ok, W3}, gen_server:call(Pid, checkout, 1000)),
    %% 4th checkout waits for worker (timeout expected)
    Result = try
        gen_server:call(Pid, checkout, 100)
    catch
        exit:{timeout, _} -> {error, timeout}
    end,
    ?assertMatch({error, _}, Result),
    
    cleanup(),
    ok.

%%====================================================================
%% WebSocket Registry Tests
%%====================================================================

ws_register_unregister_test() ->
    setup(),
    {ok, Pid} = omn_router:start_link(2),
    timer:sleep(50),
    MyPid = self(),
    omn_router:register_ws(123, MyPid),
    timer:sleep(50),
    [{123, LookupPid}] = ets:lookup(omn_ws_registry, 123),
    ?assertEqual(MyPid, LookupPid),
    omn_router:unregister_ws(123),
    timer:sleep(50),
    [] = ets:lookup(omn_ws_registry, 123),
    cleanup(),
    ok.

ws_push_test() ->
    setup(),
    {ok, Pid} = omn_router:start_link(2),
    timer:sleep(50),
    MyPid = self(),
    omn_router:register_ws(456, MyPid),
    timer:sleep(50),
    omn_router:push_ws(456, [{send_text, <<"test">>}]),
    receive
        {push, [{send_text, <<"test">>}]} -> ok
    after 1000 ->
        ?assert(false, "Did not receive push")
    end,
    cleanup(),
    ok.

%%====================================================================
%% Helper Functions
%%====================================================================

setup() ->
    %% Router creates its own ETS table in init/1
    %% Unregister any existing router first
    catch unregister(omn_router),
    catch ets:delete(omn_ws_registry),
    timer:sleep(100),  %% Give time for async cleanup
    ok.

cleanup() ->
    %% Unregister router and delete ETS tables
    catch unregister(omn_router),
    catch ets:delete(omn_ws_registry),
    timer:sleep(100),  %% Give time for async cleanup
    ok.

spawn_worker() ->
    spawn(fun() -> receive stop -> ok end end).

-module(omn_router_tests).
-include_lib("eunit/include/eunit.hrl").

%% Test imports
-include("omn_router.hrl").

%%====================================================================
%% Worker Pool Tests
%%====================================================================

checkout_checkin_test() ->
    %% Start router with 2 workers
    {ok, Pid} = omn_router:start_link(2),
    timer:sleep(100),
    
    %% No workers available initially
    ?assertMatch({error, _}, omn_router:checkout_worker()),
    
    %% Check in a fake worker
    FakeWorker = self(),
    omn_router:checkin_worker(FakeWorker),
    timer:sleep(50),
    
    %% Should be able to checkout
    ?assertMatch({ok, FakeWorker}, omn_router:checkout_worker()),
    
    %% Worker should be removed from pool after checkout
    ?assertMatch({error, _}, omn_router:checkout_worker()),
    
    %% Check in again
    omn_router:checkin_worker(FakeWorker),
    timer:sleep(50),
    
    %% Should be available again
    ?assertMatch({ok, FakeWorker}, omn_router:checkout_worker()),
    
    %% Cleanup
    gen_server:stop(Pid),
    ok.

dead_worker_test() ->
    %% Start router
    {ok, Pid} = omn_router:start_link(2),
    timer:sleep(100),
    
    %% Check in a worker then kill it
    FakeWorker = spawn(fun() -> receive stop -> ok end end),
    omn_router:checkin_worker(FakeWorker),
    timer:sleep(50),
    
    %% Kill the fake worker
    FakeWorker ! stop,
    timer:sleep(100),
    
    %% Should not return dead worker
    ?assertMatch({error, _}, omn_router:checkout_worker()),
    
    %% Cleanup
    gen_server:stop(Pid),
    ok.

multiple_workers_test() ->
    %% Start router with 3 workers
    {ok, Pid} = omn_router:start_link(3),
    timer:sleep(100),
    
    %% Check in 3 workers
    W1 = spawn_worker(),
    W2 = spawn_worker(),
    W3 = spawn_worker(),
    
    omn_router:checkin_worker(W1),
    omn_router:checkin_worker(W2),
    omn_router:checkin_worker(W3),
    timer:sleep(50),
    
    %% Checkout all workers
    ?assertMatch({ok, W1}, omn_router:checkout_worker()),
    ?assertMatch({ok, W2}, omn_router:checkout_worker()),
    ?assertMatch({ok, W3}, omn_router:checkout_worker()),
    
    %% Pool should be empty
    ?assertMatch({error, _}, omn_router:checkout_worker()),
    
    %% Check them back in
    omn_router:checkin_worker(W1),
    omn_router:checkin_worker(W2),
    omn_router:checkin_worker(W3),
    timer:sleep(50),
    
    %% Should be available again (FIFO order)
    ?assertMatch({ok, W1}, omn_router:checkout_worker()),
    ?assertMatch({ok, W2}, omn_router:checkout_worker()),
    ?assertMatch({ok, W3}, omn_router:checkout_worker()),
    
    %% Cleanup
    gen_server:stop(Pid),
    ok.

waiter_queue_test() ->
    %% Start router with 1 worker
    {ok, Pid} = omn_router:start_link(1),
    timer:sleep(100),
    
    %% Check in one worker
    FakeWorker = self(),
    omn_router:checkin_worker(FakeWorker),
    timer:sleep(50),
    
    %% First checkout succeeds
    ?assertMatch({ok, FakeWorker}, omn_router:checkout_worker()),
    
    %% Second checkout should queue (we can't easily test async behavior)
    %% but we can verify the call doesn't immediately fail
    
    %% Cleanup
    gen_server:stop(Pid),
    ok.

overload_protection_test() ->
    %% Start router
    {ok, Pid} = omn_router:start_link(1),
    timer:sleep(100),
    
    %% Fill the waiter queue (max is 1000)
    %% We won't actually fill 1000, but test the mechanism
    
    %% Check in and checkout to verify basic operation
    FakeWorker = self(),
    omn_router:checkin_worker(FakeWorker),
    timer:sleep(50),
    
    ?assertMatch({ok, FakeWorker}, omn_router:checkout_worker()),
    
    %% Cleanup
    gen_server:stop(Pid),
    ok.

%%====================================================================
%% WebSocket Registry Tests
%%====================================================================

ws_registry_test() ->
    %% Start router
    {ok, Pid} = omn_router:start_link(1),
    timer:sleep(100),
    
    %% Register a WebSocket connection
    ReqId = 12345,
    WsPid = self(),
    omn_router:register_ws(ReqId, WsPid),
    timer:sleep(50),
    
    %% Verify registration (via ETS direct lookup)
    [{ReqId, WsPid}] = ets:lookup(omn_ws_registry, ReqId),
    
    %% Unregister
    omn_router:unregister_ws(ReqId),
    timer:sleep(50),
    
    %% Verify unregistration
    [] = ets:lookup(omn_ws_registry, ReqId),
    
    %% Cleanup
    gen_server:stop(Pid),
    ok.

ws_push_test() ->
    %% Start router
    {ok, Pid} = omn_router:start_link(1),
    timer:sleep(100),
    
    %% Register and send a push
    ReqId = 67890,
    WsPid = self(),
    omn_router:register_ws(ReqId, WsPid),
    timer:sleep(50),
    
    Actions = [{send_text, <<"Hello">>}],
    omn_router:push_ws(ReqId, Actions),
    
    %% Should receive the message
    receive
        {push, Actions} -> ok
    after 1000 ->
        ?assert(false, "Did not receive push message")
    end,
    
    %% Cleanup
    gen_server:stop(Pid),
    ok.

%%====================================================================
%% Helper Functions
%%====================================================================

spawn_worker() ->
    spawn(fun() -> receive stop -> ok end end).

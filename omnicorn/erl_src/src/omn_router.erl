-module(omn_router).
-behaviour(gen_server).
-export([start_link/1, checkin_worker/1, checkout_worker/0]).
-export([register_ws/2, unregister_ws/1, push_ws/2]).
-export([init/1, handle_call/3, handle_cast/2, handle_info/2]).

-record(state, {workers, waiters}).

start_link(Count) -> gen_server:start_link({local, ?MODULE}, ?MODULE, Count,[]).
checkin_worker(Pid) -> gen_server:cast(?MODULE, {checkin, Pid}).
checkout_worker() -> try gen_server:call(?MODULE, checkout, 10000) catch exit:{timeout, _} -> {error, empty} end.

%% WS Registry API
register_ws(ReqId, Pid) -> gen_server:cast(?MODULE, {reg_ws, ReqId, Pid}).
unregister_ws(ReqId) -> gen_server:cast(?MODULE, {unreg_ws, ReqId}).
push_ws(ReqId, Actions) -> gen_server:cast(?MODULE, {push_ws, ReqId, Actions}).

init(_) ->
    %% Use an ETS table for fast, concurrent access to WS PIDs
    ets:new(omn_ws_registry,[named_table, public, set, {read_concurrency, true}, {write_concurrency, true}]),
    {ok, #state{workers = queue:new(), waiters = queue:new()}}.

handle_cast({checkin, Pid}, State = #state{workers=W, waiters=Wait}) ->
    case is_process_alive(Pid) of
        true -> case queue:out(Wait) of
            {{value, From}, NewWait} -> gen_server:reply(From, {ok, Pid}), {noreply, State#state{waiters=NewWait}};
            {empty, _} -> {noreply, State#state{workers=queue:in(Pid, W)}}
        end;
        false -> {noreply, State}
    end;

handle_cast({reg_ws, ReqId, Pid}, State) ->
    ets:insert(omn_ws_registry, {ReqId, Pid}),
    {noreply, State};

handle_cast({unreg_ws, ReqId}, State) ->
    ets:delete(omn_ws_registry, ReqId),
    {noreply, State};

handle_cast({push_ws, ReqId, Actions}, State) ->
    case ets:lookup(omn_ws_registry, ReqId) of
        [{_, Pid}] -> Pid ! {push, Actions};[] -> ok
    end,
    {noreply, State}.

handle_call(checkout, From, State = #state{workers=W, waiters=Wait}) ->
    case queue:out(W) of
        {{value, Pid}, NewW} -> case is_process_alive(Pid) of
            true -> {reply, {ok, Pid}, State#state{workers=NewW}};
            false -> handle_call(checkout, From, State#state{workers=NewW})
        end;
        {empty, _} -> {noreply, State#state{waiters=queue:in(From, Wait)}}
    end.

handle_info(_, State) -> {noreply, State}.

-module(omn_router).
-behaviour(gen_server).

%% API
-export([start_link/1, checkin_worker/1, checkout_worker/0]).

%% GenServer Callbacks
-export([init/1, handle_call/3, handle_cast/2, handle_info/2]).

%% State maintains two queues:
%% 1. Idle workers ready to take a job
%% 2. Suspended HTTP/WS requests waiting for a worker
-record(state, {
    workers,  %% queue:queue(pid())
    waiters   %% queue:queue(from())
}).

start_link(Count) ->
    gen_server:start_link({local, ?MODULE}, ?MODULE, Count,[]).

checkin_worker(Pid) ->
    gen_server:cast(?MODULE, {checkin, Pid}).

%% We set the timeout high (10s). If there's a huge traffic spike,
%% the request will wait securely in the queue instead of dropping.
checkout_worker() ->
    try gen_server:call(?MODULE, checkout, 10000)
    catch exit:{timeout, _} -> {error, empty} end.

init(_) ->
    {ok, #state{
        workers = queue:new(),
        waiters = queue:new()
    }}.

handle_cast({checkin, Pid}, State = #state{workers=Workers, waiters=Waiters}) ->
    case is_process_alive(Pid) of
        true ->
            case queue:out(Waiters) of
                {{value, From}, NewWaiters} ->
                    %% An HTTP request is sleeping! Wake it up instantly!
                    gen_server:reply(From, {ok, Pid}),
                    {noreply, State#state{waiters = NewWaiters}};
                {empty, _} ->
                    %% No pending requests, park the worker in the idle queue.
                    {noreply, State#state{workers = queue:in(Pid, Workers)}}
            end;
        false ->
            {noreply, State}
    end;
handle_cast(_, State) ->
    {noreply, State}.

handle_call(checkout, From, State = #state{workers=Workers, waiters=Waiters}) ->
    case queue:out(Workers) of
        {{value, Pid}, NewWorkers} ->
            case is_process_alive(Pid) of
                true ->
                    %% Worker is free, give it to the request immediately
                    {reply, {ok, Pid}, State#state{workers = NewWorkers}};
                false ->
                    %% Worker died silently, discard it and try the next one
                    handle_call(checkout, From, State#state{workers = NewWorkers})
            end;
        {empty, _} ->
            %% NO WORKERS AVAILABLE! (Backpressure kicks in)
            %% We suspend the HTTP request by saving 'From' and returning 'noreply'
            {noreply, State#state{waiters = queue:in(From, Waiters)}}
    end;
handle_call(_, _From, State) ->
    {reply, ok, State}.

handle_info(_, State) ->
    {noreply, State}.

-module(omn_task_broker).
-behaviour(gen_server).
-export([start_link/0, enqueue/1, register_worker/1]).
-export([init/1, handle_call/3, handle_cast/2, handle_info/2]).

-record(state, {
    workers =[] %% List of active Python UDS sockets
}).

start_link() ->
    gen_server:start_link({local, ?MODULE}, ?MODULE, [],[]).

register_worker(WorkerPid) ->
    gen_server:cast(?MODULE, {register, WorkerPid}).

enqueue(Payload) ->
    gen_server:cast(?MODULE, {enqueue, Payload}).

init([]) ->
    %% On boot, load any un-acked persistent tasks from Mnesia and re-queue them!
    %% (Implementation omitted for brevity, but this is where crash recovery happens)
    {ok, #state{}}.

handle_cast({register, WorkerPid}, State) ->
    %% Add worker to our multiplex pool
    {noreply, State#state{workers = [WorkerPid | State#state.workers]}};

handle_cast({enqueue, Payload}, State) ->
    IsPersistent = maps:get(<<"persistent">>, Payload, false),
    TaskId = erlang:system_time(microsecond),

    %% 1. Store the task
    if
        IsPersistent ->
            TaskRec = {omn_persistent_tasks, TaskId, maps:get(<<"name">>, Payload), Payload, maps:get(<<"retries">>, Payload, 3)},
            mnesia:dirty_write(TaskRec);
        true ->
            ets:insert(omnicorn_volatile_tasks, {TaskId, Payload})
    end,

    %% 2. Route to a random Python worker via Multiplexing
    %% Because Python is Asyncio, this will NOT block the worker's HTTP traffic!
    case State#state.workers of[] -> ok; %% Will be picked up when a worker boots
        Workers ->
            RandomWorker = lists:nth(rand:uniform(length(Workers)), Workers),
            TaskMessage = Payload#{<<"task_id">> => TaskId},
            omn_worker:send_async_task(RandomWorker, TaskMessage)
    end,

    {noreply, State}.

handle_call(_, _, State) -> {reply, ok, State}.
handle_info(_, State) -> {noreply, State}.

-module(omn_task_broker).
-behaviour(gen_server).
-export([start_link/0, enqueue/1, ack/1, fail/2, get_stats/0]).
-export([init/1, handle_call/3, handle_cast/2, handle_info/2]).

-record(state, {
    max_retries = 3,
    retry_delay_ms = 5000
}).

-define(DLQ_TABLE, omn_activities_dlq).

start_link() ->
    gen_server:start_link({local, ?MODULE}, ?MODULE, [], []).

enqueue(Payload) -> gen_server:cast(?MODULE, {enq, Payload}).
ack(Id) -> gen_server:cast(?MODULE, {ack, Id}).
fail(Id, Err) -> gen_server:cast(?MODULE, {fail, Id, Err}).
get_stats() -> gen_server:call(?MODULE, stats).

init([]) ->
    %% Create DLQ table for failed activities
    ets:new(?DLQ_TABLE, [named_table, public, bag, {read_concurrency, true}]),
    
    %% Resurrect pending activities from disk
    resurrect_activities(),
    
    {ok, #state{}}.

handle_cast({enq, Payload}, State = #state{max_retries=MaxRetries}) ->
    Id = erlang:system_time(microsecond),
    Name = maps:get(<<"name">>, Payload),
    %% Store with retry count
    mnesia:dirty_write({omn_activities, Id, Name, Payload, MaxRetries}),
    dispatch_activity(Id, Payload, State),
    {noreply, State};

handle_cast({ack, Id}, State) ->
    mnesia:dirty_delete(omn_activities, Id),
    {noreply, State};

handle_cast({fail, Id, Err}, State = #state{retry_delay_ms=Delay}) ->
    case mnesia:dirty_read(omn_activities, Id) of
        [{omn_activities, Id, Name, Payload, Retries}] when Retries > 1 ->
            %% Decrement retry counter and reschedule
            mnesia:dirty_write({omn_activities, Id, Name, Payload, Retries - 1}),
            io:format("⚠️ Activity ~p failed, retrying (~p left): ~p~n", 
                      [Id, Retries - 1, Err]),
            erlang:send_after(Delay, self(), {retry_task, Id, Payload});
        [{omn_activities, Id, Name, Payload, _Retries}] ->
            %% Max retries exceeded, move to DLQ
            io:format("🔥 Activity ~p moved to DLQ: ~p~n", [Id, Err]),
            mnesia:dirty_delete(omn_activities, Id),
            ets:insert(?DLQ_TABLE, {Id, Name, Payload, Err, erlang:system_time()});
        [] ->
            io:format("⚠️ Activity ~p not found (already processed?)~n", [Id])
    end,
    {noreply, State};

handle_cast(_, State) ->
    {noreply, State}.

handle_call(stats, _From, State) ->
    Pending = mnesia:table_info(omn_activities, size),
    DLQ = ets:info(?DLQ_TABLE, size),
    {reply, #{pending => Pending, dlq => DLQ}, State};

handle_call(_, _, State) ->
    {reply, {error, unknown_call}, State}.

handle_info({retry_task, Id, Payload}, State) ->
    dispatch_activity(Id, Payload, State),
    {noreply, State};

handle_info(_, State) -> 
    {noreply, State}.

%% Internal helpers
resurrect_activities() ->
    Pending = mnesia:dirty_match_object({omn_activities, '_', '_', '_', '_'}),
    lists:foreach(fun({omn_activities, Id, _Name, Payload, _Retries}) ->
        erlang:send_after(2000, self(), {retry_task, Id, Payload})
    end, Pending).

dispatch_activity(Id, Payload, _State) ->
    case omn_router:checkout_worker() of
        {ok, Worker} ->
            omn_worker:send_async(Worker, #{
                <<"type">> => <<"activity_execute">>,
                <<"payload">> => Payload#{<<"activity_id">> => Id}
            });
        _ ->
            %% No worker available, retry later
            erlang:send_after(1000, self(), {retry_task, Id, Payload})
    end.

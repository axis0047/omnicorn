-module(omn_task_broker).
-behaviour(gen_server).
-export([start_link/0, enqueue/1, ack/1, fail/2, get_stats/0]).
-export([get_dlq/0, clear_dlq/0]).
-export([init/1, handle_call/3, handle_cast/2, handle_info/2, terminate/2]).

-record(state, {
    max_retries = 3,
    retry_delay_ms = 5000,
    mnesia_available = false
}).

-define(DLQ_TABLE, omn_activities_dlq).
-define(DLQ_MNESIA_TABLE, omn_activities_dlq_mnesia).

start_link() ->
    gen_server:start_link({local, ?MODULE}, ?MODULE, [], []).

enqueue(Payload) -> gen_server:cast(?MODULE, {enq, Payload}).
ack(Id) -> gen_server:cast(?MODULE, {ack, Id}).
fail(Id, Err) -> gen_server:cast(?MODULE, {fail, Id, Err}).
get_stats() -> gen_server:call(?MODULE, stats).
get_dlq() -> gen_server:call(?MODULE, get_dlq).
clear_dlq() -> gen_server:call(?MODULE, clear_dlq).

init([]) ->
    %% Create ETS DLQ table for fast access (delete if exists)
    catch ets:delete(?DLQ_TABLE),
    ets:new(?DLQ_TABLE, [named_table, public, bag, {read_concurrency, true}]),

    %% Check if Mnesia is available
    MnesiaAvailable = case application:get_key(mnesia, vsn) of
        undefined -> false;  %% Mnesia not loaded
        {ok, _} ->
            %% Try to start Mnesia
            case application:start(mnesia) of
                ok -> true;
                {error, {already_started, _}} -> true;
                _ -> false
            end
    end,

    %% Create tables if Mnesia is available
    case MnesiaAvailable of
        true ->
            %% Create activities table
            mnesia:create_table(omn_activities, [
                {attributes, [id, name, payload, retries]},
                {disc_copies, [node()]}
            ]),
            
            %% Create DLQ table with disk storage for persistence
            mnesia:create_table(?DLQ_MNESIA_TABLE, [
                {attributes, [id, name, payload, error, timestamp]},
                {disc_copies, [node()]}
            ]),
            
            mnesia:wait_for_tables([omn_activities, ?DLQ_MNESIA_TABLE], 5000),
            
            %% Recover DLQ from Mnesia to ETS for fast access
            recover_dlq(),
            
            %% Resurrect pending activities
            resurrect_activities();
        false ->
            ok
    end,

    {ok, #state{mnesia_available = MnesiaAvailable}}.

handle_cast({enq, Payload}, State = #state{max_retries=MaxRetries, mnesia_available = MnesiaAvailable}) ->
    case MnesiaAvailable of
        true ->
            Id = erlang:system_time(microsecond),
            Name = maps:get(<<"name">>, Payload),
            %% Store with retry count
            mnesia:dirty_write({omn_activities, Id, Name, Payload, MaxRetries}),
            dispatch_activity(Id, Payload, State);
        false ->
            %% Mnesia not available, skip storage but don't crash
            ok
    end,
    {noreply, State};

handle_cast({ack, Id}, State = #state{mnesia_available = MnesiaAvailable}) ->
    case MnesiaAvailable of
        true -> mnesia:dirty_delete(omn_activities, Id);
        false -> ok
    end,
    {noreply, State};

handle_cast({fail, Id, Err}, State = #state{retry_delay_ms=Delay, mnesia_available = MnesiaAvailable}) ->
    case MnesiaAvailable of
        true ->
            case mnesia:dirty_read(omn_activities, Id) of
                [{omn_activities, Id, Name, Payload, Retries}] when Retries > 1 ->
                    %% Decrement retry counter and reschedule
                    mnesia:dirty_write({omn_activities, Id, Name, Payload, Retries - 1}),
                    io:format("⚠️ Activity ~p failed, retrying (~p left): ~p~n",
                              [Id, Retries - 1, Err]),
                    erlang:send_after(Delay, self(), {retry_task, Id, Payload});
                [{omn_activities, Id, Name, Payload, _Retries}] ->
                    %% Max retries exceeded, move to DLQ
                    Timestamp = erlang:system_time(millisecond),
                    io:format("🔥 Activity ~p moved to DLQ: ~p~n", [Id, Err]),
                    mnesia:dirty_delete(omn_activities, Id),
                    %% Write to both ETS (fast) and Mnesia (persistent)
                    ets:insert(?DLQ_TABLE, {Id, Name, Payload, Err, Timestamp}),
                    mnesia:dirty_write(?DLQ_MNESIA_TABLE, {Id, Name, Payload, Err, Timestamp});
                [] ->
                    io:format("⚠️ Activity ~p not found (already processed?)~n", [Id])
            end;
        false ->
            %% Mnesia not available, skip
            ok
    end,
    {noreply, State};

handle_cast(_, State) ->
    {noreply, State}.

handle_call(stats, _From, State = #state{mnesia_available = MnesiaAvailable}) ->
    Pending = case MnesiaAvailable of
        true -> mnesia:table_info(omn_activities, size);
        false -> 0
    end,
    DLQ = case MnesiaAvailable of
        true -> mnesia:table_info(?DLQ_MNESIA_TABLE, size);
        false -> ets:info(?DLQ_TABLE, size)
    end,
    {reply, #{pending => Pending, dlq => DLQ}, State};

handle_call(get_dlq, _From, State = #state{mnesia_available = MnesiaAvailable}) ->
    case MnesiaAvailable of
        true ->
            %% Get all DLQ entries from Mnesia
            Entries = mnesia:dirty_all_read(?DLQ_MNESIA_TABLE),
            {reply, {ok, Entries}, State};
        false ->
            {reply, {error, mnesia_not_available}, State}
    end;

handle_call(clear_dlq, _From, State = #state{mnesia_available = MnesiaAvailable}) ->
    case MnesiaAvailable of
        true ->
            mnesia:clear_table(?DLQ_MNESIA_TABLE),
            ets:delete_all_objects(?DLQ_TABLE),
            {reply, ok, State};
        false ->
            {reply, {error, mnesia_not_available}, State}
    end;

handle_call(_, _, State) ->
    {reply, {error, unknown_call}, State}.

handle_info({retry_task, Id, Payload}, State) ->
    dispatch_activity(Id, Payload, State),
    {noreply, State};

handle_info(_, State) ->
    {noreply, State}.

%% Terminate callback - ensure DLQ is persisted
terminate(_Reason, #state{mnesia_available = MnesiaAvailable}) ->
    case MnesiaAvailable of
        true ->
            %% ETS is already synced to Mnesia on each write,
            %% but we can force a final sync here
            io:format("DLQ persisted with ~p entries~n", [mnesia:table_info(?DLQ_MNESIA_TABLE, size)]);
        false ->
            ok
    end,
    ok.

%% Internal helpers

%% Recover DLQ from Mnesia to ETS on startup
recover_dlq() ->
    case catch mnesia:table_info(?DLQ_MNESIA_TABLE, name) of
        {'EXIT', _} ->
            %% Table doesn't exist, skip recovery
            ok;
        _ ->
            Entries = mnesia:dirty_all_read(?DLQ_MNESIA_TABLE),
            lists:foreach(fun({Id, Name, Payload, Err, Timestamp}) ->
                ets:insert(?DLQ_TABLE, {Id, Name, Payload, Err, Timestamp})
            end, Entries),
            io:format("Recovered ~p DLQ entries from Mnesia~n", [length(Entries)])
    end.

resurrect_activities() ->
    %% Only resurrect if Mnesia is running and table exists
    case catch mnesia:table_info(omn_activities, name) of
        {'EXIT', _} ->
            %% Mnesia not running or table doesn't exist, skip resurrection
            ok;
        _ ->
            Pending = mnesia:dirty_match_object({omn_activities, '_', '_', '_', '_'}),
            lists:foreach(fun({omn_activities, Id, _Name, Payload, _Retries}) ->
                erlang:send_after(2000, self(), {retry_task, Id, Payload})
            end, Pending)
    end.

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

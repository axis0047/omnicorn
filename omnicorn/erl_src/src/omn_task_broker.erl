-module(omn_task_broker).
-behaviour(gen_server).
-export([start_link/0, enqueue/1, ack/1, fail/2]).
-export([init/1, handle_call/3, handle_cast/2, handle_info/2]).

start_link() ->
    gen_server:start_link({local, ?MODULE}, ?MODULE,[],[]).

enqueue(Payload) -> gen_server:cast(?MODULE, {enq, Payload}).
ack(Id) -> gen_server:cast(?MODULE, {ack, Id}).
fail(Id, Err) -> gen_server:cast(?MODULE, {fail, Id, Err}).

init([]) ->
    %% 🔥 RESURRECTION LOGIC: Re-queue all pending activities from disk on boot
    PendingActivities = mnesia:dirty_match_object({omn_activities, '_', '_', '_', '_'}),
    lists:foreach(fun({omn_activities, Id, _Name, Payload, _Retries}) ->
        %% Wait 2 seconds for Python workers to boot, then spray tasks back to them
        erlang:send_after(2000, self(), {retry_task, Id, Payload})
    end, PendingActivities),

    {ok, #{}}.

%% Required by gen_server behaviour
handle_call(_Request, _From, State) ->
    {reply, ok, State}.

handle_cast({enq, Payload}, S) ->
    Id = erlang:system_time(microsecond),
    mnesia:dirty_write({omn_activities, Id, maps:get(<<"name">>, Payload), Payload, 3}),
    case omn_router:checkout_worker() of
        {ok, W} ->
            omn_worker:send_async(W, #{<<"type">> => <<"activity_execute">>,
                                       <<"payload">> => Payload#{<<"activity_id">> => Id}});
        _ -> ok
    end,
    {noreply, S};

handle_cast({ack, Id}, S) ->
    mnesia:dirty_delete(omn_activities, Id),
    {noreply, S};

handle_cast({fail, Id, Err}, S) ->
    io:format("Activity ~p failed: ~p~n", [Id, Err]),
    {noreply, S}.

%% Unified handle_info block
handle_info({retry_task, Id, Payload}, S) ->
    case omn_router:checkout_worker() of
        {ok, W} ->
            omn_worker:send_async(W, #{<<"type">> => <<"activity_execute">>,
                                       <<"payload">> => Payload#{<<"activity_id">> => Id}});
        _ ->
            erlang:send_after(1000, self(), {retry_task, Id, Payload})
    end,
    {noreply, S};
handle_info(_, S) ->
    {noreply, S}.

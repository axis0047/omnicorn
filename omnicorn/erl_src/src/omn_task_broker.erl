-module(omn_task_broker).
-behaviour(gen_server).
-export([start_link/0, enqueue/1, ack/1, fail/2]).
-export([init/1, handle_cast/2, handle_info/2]).

start_link() -> gen_server:start_link({local, ?MODULE}, ?MODULE, [],[]).
enqueue(Payload) -> gen_server:cast(?MODULE, {enq, Payload}).
ack(Id) -> gen_server:cast(?MODULE, {ack, Id}).
fail(Id, Err) -> gen_server:cast(?MODULE, {fail, Id, Err}).

init([]) -> {ok, #{}}.

handle_cast({enq, Payload}, S) ->
    Id = erlang:system_time(microsecond),
    mnesia:dirty_write({omn_activities, Id, maps:get(<<"name">>, Payload), Payload, 3}),
    case omn_router:checkout_worker() of
        {ok, W} -> omn_worker:send_async(W, #{<<"type">> => <<"activity_execute">>, <<"payload">> => Payload#{<<"activity_id">> => Id}});
        _ -> ok
    end, {noreply, S};
handle_cast({ack, Id}, S) -> mnesia:dirty_delete(omn_activities, Id), {noreply, S};
handle_cast({fail, Id, Err}, S) -> io:format("Activity ~p failed: ~p~n", [Id, Err]), {noreply, S}.
handle_info(_, S) -> {noreply, S}.

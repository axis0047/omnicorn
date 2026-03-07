-module(omn_router).
-behaviour(gen_server).
-export([start_link/1, checkin_worker/1, checkout_worker/0]).
-export([init/1, handle_call/3, handle_cast/2, handle_info/2]).

start_link(Count) ->
    gen_server:start_link({local, ?MODULE}, ?MODULE, Count, []).

checkin_worker(Pid) ->
    gen_server:cast(?MODULE, {checkin, Pid}).

checkout_worker() ->
    gen_server:call(?MODULE, checkout).

%% State is just a Queue of Pids
init(_) ->
    {ok, queue:new()}.

handle_cast({checkin, Pid}, Queue) ->
    %% Add worker back to the pool
    {noreply, queue:in(Pid, Queue)}.

handle_call(checkout, _From, Queue) ->
    case queue:out(Queue) of
        {{value, Pid}, NewQueue} ->
            %% Verify worker is actually alive before handing it out
            case is_process_alive(Pid) of
                true ->
                    {reply, {ok, Pid}, NewQueue};
                false ->
                    %% Recursively try next if this one died silently
                    handle_call(checkout, _From, NewQueue)
            end;
        {empty, _} ->
            %% No workers available (Backpressure)
            {reply, {error, empty}, Queue}
    end.

handle_info(_, State) -> {noreply, State}.

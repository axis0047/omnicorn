-module(omn_cache_cleanup).
-behaviour(gen_server).

%% API
-export([start_link/0, cleanup/0]).

%% gen_server callbacks
-export([init/1, handle_call/3, handle_cast/2, handle_info/2, terminate/2, code_change/3]).

-define(CLEANUP_INTERVAL, 60000). %% Run every 60 seconds

start_link() ->
    gen_server:start_link({local, ?MODULE}, ?MODULE, [], []).

cleanup() ->
    gen_server:cast(?MODULE, cleanup).

init([]) ->
    %% Schedule first cleanup
    schedule_cleanup(),
    {ok, #{}}.

handle_call(_Request, _From, State) ->
    {reply, ok, State}.

handle_cast(cleanup, State) ->
    do_cleanup(),
    schedule_cleanup(),
    {noreply, State};

handle_cast(_, State) ->
    {noreply, State}.

handle_info(cleanup, State) ->
    do_cleanup(),
    schedule_cleanup(),
    {noreply, State};

handle_info(_Info, State) ->
    {noreply, State}.

terminate(_Reason, _State) ->
    ok.

code_change(_OldVsn, State, _Extra) ->
    {ok, State}.

%% Internal functions

schedule_cleanup() ->
    erlang:send_after(?CLEANUP_INTERVAL, self(), cleanup).

do_cleanup() ->
    Now = erlang:system_time(millisecond),
    Removed = ets:foldl(fun({Key, _Val, TTL}, Acc) when TTL > 0 andalso Now > TTL ->
        ets:delete(omnicorn_cache, Key),
        Acc + 1;
        (_, Acc) -> Acc
    end, 0, omnicorn_cache),
    
    if
        Removed > 0 ->
            io:format("Cache cleanup: removed ~p expired entries~n", [Removed]);
        true ->
            ok
    end.

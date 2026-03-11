-module(omn_workflow_actor).
-behaviour(gen_server).
-export([start_link/4, init/1, handle_call/3, handle_cast/2, handle_info/2]).
-record(state, {id, name, step, data}).

start_link(Id, Name, Step, Data) ->
    gen_server:start_link(?MODULE, [Id, Name, Step, Data], []).

init([Id, Name, Step, Data]) ->
    mnesia:dirty_write({omn_sagas, Id, Name, Step, Data}),
    gen_server:cast(self(), execute),
    {ok, #state{id=Id, name=Name, step=Step, data=Data}}.

%% Required by gen_server behaviour
handle_call(_Request, _From, State) ->
    {reply, ok, State}.

handle_cast(execute, S) ->
    case omn_router:checkout_worker() of
        {ok, Worker} ->
            Msg = #{<<"type">> => <<"workflow_execute">>,
                    <<"payload">> => #{<<"workflow_id">> => S#state.id,
                                       <<"name">> => S#state.name,
                                       <<"step">> => S#state.step,
                                       <<"data">> => S#state.data}},
            omn_worker:send_async(Worker, Msg);
        _ ->
            erlang:send_after(1000, self(), execute) %% Retry if workers full
    end,
    {noreply, S};

handle_cast({checkpoint, <<"__finished__">>, _, _}, S) ->
    mnesia:dirty_delete(omn_sagas, S#state.id),
    ets:delete(active_actors, S#state.id),
    {stop, normal, S};

handle_cast({checkpoint, NextStep, SleepMs, Data}, S) ->
    mnesia:dirty_write({omn_sagas, S#state.id, S#state.name, NextStep, Data}),
    if
        SleepMs > 0 ->
            erlang:send_after(SleepMs, self(), execute),
            {noreply, S#state{step=NextStep, data=Data}, hibernate};
        true ->
            gen_server:cast(self(), execute),
            {noreply, S#state{step=NextStep, data=Data}}
    end.

handle_info(execute, S) ->
    gen_server:cast(self(), execute),
    {noreply, S};
handle_info(_Info, S) ->
    {noreply, S}.

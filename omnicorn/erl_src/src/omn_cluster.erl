-module(omn_cluster).
-behaviour(gen_server).

%% API
-export([start_link/0, join/1, leave/0, status/0, connected_nodes/0]).

%% gen_server callbacks
-export([init/1, handle_call/3, handle_cast/2, handle_info/2, terminate/2, code_change/3]).

-record(state, {
    node_name,
    cookie,
    discovery_nodes = [],
    connected = false
}).

%%====================================================================
%% API
%%====================================================================

start_link() ->
    gen_server:start_link({local, ?MODULE}, ?MODULE, [], []).

join(NodeList) when is_list(NodeList) ->
    gen_server:cast(?MODULE, {join, NodeList}).

leave() ->
    gen_server:cast(?MODULE, leave).

status() ->
    gen_server:call(?MODULE, status).

connected_nodes() ->
    gen_server:call(?MODULE, connected_nodes).

%%====================================================================
%% gen_server callbacks
%%====================================================================

init([]) ->
    NodeName = list_to_atom(os:getenv("OMNICORN_NODE", "omnicorn@127.0.0.1")),
    Cookie = os:getenv("OMNICORN_COOKIE", "omnicorn_dev_cookie"),
    ClusterEnabled = os:getenv("OMNICORN_CLUSTER_ENABLED", "false"),
    
    %% Set cookie for distributed Erlang
    erlang:set_cookie(node(), list_to_atom(Cookie)),
    
    io:format("Cluster configuration:~n"),
    io:format("  Node: ~p~n", [NodeName]),
    io:format("  Enabled: ~p~n", [ClusterEnabled]),
    
    {ok, #state{
        node_name = NodeName,
        cookie = Cookie,
        discovery_nodes = [],
        connected = ClusterEnabled =:= "true"
    }}.

handle_call(status, _From, State) ->
    Status = #{
        node => node(),
        node_name => State#state.node_name,
        connected => State#state.connected,
        connected_nodes => nodes(),
        discovery_nodes => State#state.discovery_nodes
    },
    {reply, Status, State};

handle_call(connected_nodes, _From, State) ->
    {reply, nodes(), State};

handle_call(_Request, _From, State) ->
    {reply, {error, unknown_call}, State}.

handle_cast({join, NodeList}, State) ->
    io:format("Attempting to join cluster: ~p~n", [NodeList]),
    
    Results = lists:map(fun(Node) ->
        NodeAtom = list_to_atom(Node),
        case net_kernel:connect_node(NodeAtom) of
            true ->
                io:format("Connected to node: ~p~n", [NodeAtom]),
                %% Sync Mnesia tables
                case mnesia:change_config(extra_db_nodes, [NodeAtom]) of
                    {ok, [_]} ->
                        io:format("Mnesia synced with ~p~n", [NodeAtom]);
                    {error, Reason} ->
                        io:format("Mnesia sync failed: ~p~n", [Reason])
                end,
                {connected, NodeAtom};
            false ->
                io:format("Failed to connect to node: ~p~n", [NodeAtom]),
                {failed, NodeAtom}
        end
    end, NodeList),
    
    {noreply, State#state{discovery_nodes = NodeList}};

handle_cast(leave, State) ->
    lists:foreach(fun(Node) ->
        net_kernel:disconnect(Node)
    end, nodes()),
    io:format("Left cluster~n"),
    {noreply, State#state{connected = false}};

handle_cast(_Msg, State) ->
    {noreply, State}.

handle_info(_Info, State) ->
    {noreply, State}.

terminate(_Reason, _State) ->
    ok.

code_change(_OldVsn, State, _Extra) ->
    {ok, State}.

-module(omn_ws_handler).
-behaviour(cowboy_websocket).
-export([init/2, websocket_init/1, websocket_handle/2, websocket_info/2, websocket_terminate/3]).

-record(state, {
    req,
    pid,                     % The Python worker PID
    worker_id,               % ID of the Python worker
    req_id,                  % Unique request ID for this WS connection
    connection_state = #{}   % State carried to/from Python
}).

init(Req, _Opts) ->
    %% FIX 1: Store Req in state so websocket_handle/2 can access it,
    %% since Cowboy 2.x websocket callbacks no longer receive Req.
    State = #state{req = Req},
    {cowboy_websocket, Req, State}.

websocket_init(State = #state{}) ->
    io:format("[WS] Handshake successful for ~p~n", [State#state.req_id]),
    {ok, State}.

%% FIX 2: Cowboy 2.x websocket_handle/2 takes (Frame, State) — no Req argument.
websocket_handle({text, Data}, State = #state{req = Req, pid = PyPid, req_id = ReqId, connection_state = ConnState}) ->
    PythonMsg = #{
        <<"id">>      => ReqId,
        <<"type">>    => <<"websocket_message">>,
        <<"payload">> => #{
            <<"path">>             => cowboy_req:path(Req),
            <<"query">>            => cowboy_req:qs(Req),
            <<"scheme">>           => cowboy_req:scheme(Req),
            <<"port">>             => cowboy_req:port(Req),
            <<"headers">>          => cowboy_req:headers(Req),
            <<"message_type">>     => <<"text">>,
            <<"content">>          => Data,
            <<"client_info">>      => get_client_info(Req),
            <<"connection_state">> => ConnState
        }
    },
    handle_python_ws_response(PyPid, PythonMsg, ConnState, State);

websocket_handle({binary, Data}, State = #state{req = Req, pid = PyPid, req_id = ReqId, connection_state = ConnState}) ->
    PythonMsg = #{
        <<"id">>      => ReqId,
        <<"type">>    => <<"websocket_message">>,
        <<"payload">> => #{
            <<"path">>             => cowboy_req:path(Req),
            <<"query">>            => cowboy_req:qs(Req),
            <<"scheme">>           => cowboy_req:scheme(Req),
            <<"port">>             => cowboy_req:port(Req),
            <<"headers">>          => cowboy_req:headers(Req),
            <<"message_type">>     => <<"binary">>,
            <<"content">>          => Data,
            <<"client_info">>      => get_client_info(Req),
            <<"connection_state">> => ConnState
        }
    },
    handle_python_ws_response(PyPid, PythonMsg, ConnState, State);

websocket_handle(_Any, State) ->
    {ok, State}.

%% FIX 3: websocket_info/2 takes (Info, State) — no Req argument.
websocket_info(_Info, State) ->
    {ok, State}.

%% websocket_terminate/3 keeps (Reason, Req, State) — this signature is correct.
websocket_terminate(Reason, _Req, State = #state{req = Req, pid = PyPid, req_id = ReqId, connection_state = ConnState}) ->
    io:format("[WS] Connection ~p for worker ~p terminated. Reason: ~p~n",
              [ReqId, State#state.worker_id, Reason]),

    PythonMsg = #{
        <<"id">>      => ReqId,
        <<"type">>    => <<"websocket_disconnect">>,
        <<"payload">> => #{
            <<"path">>             => cowboy_req:path(Req),
            <<"query">>            => cowboy_req:qs(Req),
            <<"scheme">>           => cowboy_req:scheme(Req),
            <<"port">>             => cowboy_req:port(Req),
            <<"headers">>          => cowboy_req:headers(Req),
            <<"code">>             => get_close_code(Reason),
            <<"client_info">>      => get_client_info(Req),
            <<"connection_state">> => ConnState
        }
    },
    omn_worker:call_python(PyPid, <<"websocket_disconnect">>, PythonMsg),
    ok.

%% FIX 4: Extracted shared response-handling logic to eliminate duplication
%% and fix the missing comma before the wildcard clause (original line 53 crash).
handle_python_ws_response(PyPid, PythonMsg, ConnState, State) ->
    case omn_worker:call_python(PyPid, <<"websocket_message">>, PythonMsg) of
        {ok, PythonResponse} ->
            NewConnState = maps:get(<<"connection_state">>, PythonResponse, ConnState),
            case maps:get(<<"websocket_message_response">>, PythonResponse, []) of
                Messages when is_list(Messages) ->
                    Actions = lists:foldl(fun(Msg, Acc) ->
                        %% FIX 5: Missing comma before wildcard clause caused
                        %% "syntax error before: _" on line 53 (and equivalent binary block).
                        case maps:get(<<"type">>, Msg, <<"unknown">>) of
                            <<"send_text">>   -> Acc ++ [{reply, {text,   maps:get(<<"content">>, Msg)}}];
                            <<"send_binary">> -> Acc ++ [{reply, {binary, maps:get(<<"content">>, Msg)}}];
                            <<"close">>       -> Acc ++ [{close, maps:get(<<"code">>, Msg, 1000)}];
                            _                 -> Acc
                        end
                    end, [], Messages),
                    {Actions, State#state{connection_state = NewConnState}};
                _ ->
                    io:format("[WS] Worker ~p sent malformed WS message response: ~p~n",
                              [State#state.worker_id, PythonResponse]),
                    {close, 1001, State}
            end;
        {error, timeout} ->
            io:format("[WS] Worker ~p timed out on WS message~n", [State#state.worker_id]),
            {close, 1001, State};
        {error, Reason} ->
            io:format("[WS] Worker ~p crashed on WS message: ~p~n", [State#state.worker_id, Reason]),
            {close, 1001, State}
    end.

%% FIX 6: inet:ntoa/1 is the correct function; inet_parse:ntoa/1 is internal/deprecated.
get_client_info(Req) ->
    {Ip, Port} = cowboy_req:peer(Req),
    {list_to_binary(inet:ntoa(Ip)), Port}.

get_close_code(normal)   -> 1000;
get_close_code(shutdown) -> 1001;
get_close_code(timeout)  -> 1008;
get_close_code(kill)     -> 1001;
get_close_code(_)        -> 1001.

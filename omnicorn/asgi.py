import asyncio
import sys
import traceback

# Store active WebSocket connections globally across the worker process
# req_id -> { "task": Task, "receive_queue": Queue, "send_queue": Queue }
WS_CONNECTIONS = {}

class ASGIAdapter:
    # We maintain a SINGLE persistent event loop per worker process
    # so background WebSocket tasks stay alive between Erlang requests.
    _loop = asyncio.new_event_loop()

    @staticmethod
    def run_phase(app, msg_type, etf_payload):
        try:
            return ASGIAdapter._loop.run_until_complete(
                ASGIAdapter._run_async(app, msg_type, etf_payload)
            )
        except Exception as e:
            sys.stderr.write(f"ASGI run_phase error:\n{traceback.format_exc()}\n")
            return {b'status': 500, b'body': b"Internal Server Error"}

    @staticmethod
    async def _run_async(app, msg_type, etf_payload):
        if msg_type == b'http':
            return await ASGIAdapter._handle_http_request(app, etf_payload)
        elif msg_type == b'websocket_handshake':
            return await ASGIAdapter._handle_websocket_handshake(app, etf_payload)
        elif msg_type == b'websocket_message':
            return await ASGIAdapter._handle_websocket_message(app, etf_payload)
        elif msg_type == b'websocket_disconnect':
            return await ASGIAdapter._handle_websocket_disconnect(app, etf_payload)
        else:
            return {b'status': 500, b'body': b"Unknown ASGI phase"}

    @staticmethod
    def _parse_headers(etf_payload):
        req_headers_etf = etf_payload.get(b'headers', {})
        req_headers_asgi =[]
        header_items = req_headers_etf.items() if isinstance(req_headers_etf, dict) else req_headers_etf

        for k_bin, v_bin in header_items:
            k_bytes = k_bin if isinstance(k_bin, bytes) else str(k_bin).encode('utf-8')
            v_bytes = v_bin if isinstance(v_bin, bytes) else str(v_bin).encode('utf-8')
            req_headers_asgi.append((k_bytes.lower(), v_bytes))
        return req_headers_asgi

    @staticmethod
    async def _handle_http_request(app, etf_payload):
        method = etf_payload.get(b'method', b'GET').decode('utf-8')
        path = etf_payload.get(b'path', b'/').decode('utf-8')
        query_string = etf_payload.get(b'query', b'').decode('utf-8')
        scheme = etf_payload.get(b'scheme', b'http').decode('utf-8')
        port = etf_payload.get(b'port', 80)

        req_headers_asgi = ASGIAdapter._parse_headers(etf_payload)
        body_bytes = etf_payload.get(b'body', b'')

        scope = {
            'type': 'http',
            'asgi': {'version': '3.0', 'spec_version': '2.1'},
            'http_version': '1.1',
            'method': method,
            'scheme': scheme,
            'path': path,
            'raw_path': path.encode('latin-1'),
            'query_string': query_string.encode('latin-1'),
            'headers': req_headers_asgi,
            'server': ('omnicorn', port),
            'client': ('127.0.0.1', 0),
        }

        response_state = {'status': 500, 'headers': {}, 'body': b''}
        input_queue = asyncio.Queue()
        input_queue.put_nowait({'type': 'http.request', 'body': body_bytes, 'more_body': False})

        async def receive_http():
            return await input_queue.get()

        async def send_http(message):
            if message['type'] == 'http.response.start':
                response_state['status'] = message['status']
                for k_bytes, v_bytes in message.get('headers', []):
                    response_state['headers'][k_bytes] = v_bytes
            elif message['type'] == 'http.response.body':
                response_state['body'] += message.get('body', b'')

        try:
            await app(scope, receive_http, send_http)
        except Exception:
            sys.stderr.write(f"ASGI HTTP App Error:\n{traceback.format_exc()}\n")
            response_state['status'] = 500
            response_state['body'] = b"Internal Server Error: HTTP"

        return {
            b'status': response_state['status'],
            b'headers': response_state['headers'],
            b'body': response_state['body']
        }

    @staticmethod
    async def _handle_websocket_handshake(app, etf_payload):
        req_id = etf_payload.get(b'id', 0)
        path = etf_payload.get(b'path', b'/').decode('utf-8')
        query_string = etf_payload.get(b'query', b'').decode('utf-8')
        scheme = etf_payload.get(b'scheme', b'ws').decode('utf-8')
        port = etf_payload.get(b'port', 80)
        req_headers_asgi = ASGIAdapter._parse_headers(etf_payload)

        scope = {
            'type': 'websocket',
            'asgi': {'version': '3.0', 'spec_version': '2.1'},
            'http_version': '1.1',
            'scheme': scheme,
            'path': path,
            'raw_path': path.encode('latin-1'),
            'query_string': query_string.encode('latin-1'),
            'headers': req_headers_asgi,
            'server': ('omnicorn', port),
            'client': ('127.0.0.1', 0),
            'subprotocols':[],
            'state': {},
        }

        receive_queue = asyncio.Queue()
        send_queue = asyncio.Queue()

        # Prime the connection with the initial event
        receive_queue.put_nowait({'type': 'websocket.connect'})

        WS_CONNECTIONS[req_id] = {
            'receive_queue': receive_queue,
            'send_queue': send_queue
        }

        # 🚀 SPAWN APP IN BACKGROUND
        task = ASGIAdapter._loop.create_task(app(scope, receive_queue.get, send_queue.put))
        WS_CONNECTIONS[req_id]['task'] = task

        try:
            # Wait up to 3 seconds for the app to issue an accept/close
            response_event = await asyncio.wait_for(send_queue.get(), timeout=3.0)
        except asyncio.TimeoutError:
            return {b'websocket_handshake': b'error', b'code': 1001, b'reason': b"Handshake timeout"}

        if response_event.get('type') == 'websocket.accept':
            subprotocol = response_event.get('subprotocol', b'')
            return {b'websocket_handshake': b'accept', b'subprotocol': subprotocol}
        elif response_event.get('type') == 'websocket.close':
            return {b'websocket_handshake': b'close', b'code': response_event.get('code', 1000)}
        else:
            return {b'websocket_handshake': b'error', b'code': 1002, b'reason': b"Invalid handshake message"}

    @staticmethod
    async def _handle_websocket_message(app, etf_payload):
        req_id = etf_payload.get(b'id', 0)
        conn = WS_CONNECTIONS.get(req_id)

        if not conn:
            return {b'websocket_message_response':[], b'connection_state': {}}

        msg_type = etf_payload.get(b'message_type')
        content = etf_payload.get(b'content')

        # Push incoming data to the background task
        if msg_type == b'text':
            conn['receive_queue'].put_nowait({'type': 'websocket.receive', 'text': content.decode('utf-8')})
        elif msg_type == b'binary':
            conn['receive_queue'].put_nowait({'type': 'websocket.receive', 'bytes': content})

        # ✨ MAGIC TRICK: Yield to the event loop so the background task gets CPU time
        # to process the message we just put in the queue!
        await asyncio.sleep(0.01)

        # Collect any responses the app generated during that split-second
        erlang_responses = []
        while not conn['send_queue'].empty():
            msg = conn['send_queue'].get_nowait()
            if msg['type'] == 'websocket.send':
                if 'text' in msg:
                    erlang_responses.append({b'type': b'send_text', b'content': msg['text'].encode('utf-8')})
                elif 'bytes' in msg:
                    erlang_responses.append({b'type': b'send_binary', b'content': msg['bytes']})
            elif msg['type'] == 'websocket.close':
                erlang_responses.append({b'type': b'close', b'code': msg.get('code', 1000)})

        return {b'websocket_message_response': erlang_responses, b'connection_state': {}}

    @staticmethod
    async def _handle_websocket_disconnect(app, etf_payload):
        req_id = etf_payload.get(b'id', 0)
        conn = WS_CONNECTIONS.get(req_id)
        if conn:
            conn['receive_queue'].put_nowait({'type': 'websocket.disconnect', 'code': etf_payload.get(b'code', 1000)})
            await asyncio.sleep(0.01) # Give it time to run cleanup
            del WS_CONNECTIONS[req_id]

        return {b'websocket_disconnect_response': b'ok'}

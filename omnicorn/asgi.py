import asyncio
import sys
import traceback
import erlpack

class ASGIAdapter:
    @staticmethod
    def run(app, etf_payload):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(ASGIAdapter._run_async(app, etf_payload))
        finally:
            loop.close()

    @staticmethod
    async def _run_async(app, etf_payload):
        # Determine the scope type (http or websocket)
        scope_type = etf_payload.get(b'scope_type', b'http').decode('utf-8')

        if scope_type == 'http':
            return await ASGIAdapter._handle_http_request(app, etf_payload)
        elif scope_type == 'websocket':
            return await ASGIAdapter._handle_websocket_request(app, etf_payload)
        else:
            sys.stderr.write(f"Unknown scope type: {scope_type}\n")
            return {b'status': 500, b'body': b"Unknown scope type"}

    @staticmethod
    async def _handle_http_request(app, etf_payload):
        # Decode Erlang-native types for HTTP
        method = etf_payload[b'method'].decode('utf-8')
        path = etf_payload[b'path'].decode('utf-8')
        query_string = etf_payload[b'query'].decode('utf-8')
        scheme = etf_payload.get(b'scheme', b'http').decode('utf-8')
        port = etf_payload.get(b'port', 80)

        req_headers_etf = etf_payload.get(b'headers', [])
        req_headers_asgi = []
        for k_bin, v_bin in req_headers_etf:
            req_headers_asgi.append((k_bin.lower(), v_bin))

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

        response_state = {
            'status': 500,
            'headers': [],
            'body': b''
        }

        input_queue = asyncio.Queue()
        await input_queue.put({'type': 'http.request', 'body': body_bytes, 'more_body': False})

        async def receive_http():
            return await input_queue.get()

        async def send_http(message):
            if message['type'] == 'http.response.start':
                response_state['status'] = message['status']
                for k_bytes, v_bytes in message.get('headers', []):
                    response_state['headers'].append({erlpack.atom_from_string(k_bytes.decode('latin-1')), erlpack.term_to_binary(v_bytes)})

            elif message['type'] == 'http.response.body':
                response_state['body'] += message.get('body', b'')

        try:
            await app(scope, receive_http, send_http)
        except Exception:
            sys.stderr.write(f"ASGI HTTP App Error: {traceback.format_exc()}\n")
            response_state['status'] = 500
            response_state['body'] = b"Internal Server Error: HTTP"

        return {
            b'status': response_state['status'],
            b'headers': response_state['headers'],
            b'body': response_state['body']
        }

    @staticmethod
    async def _handle_websocket_request(app, etf_payload):
        # Decode Erlang-native types for WebSocket
        path = etf_payload[b'path'].decode('utf-8')
        query_string = etf_payload[b'query'].decode('utf-8')
        scheme = etf_payload.get(b'scheme', b'ws').decode('utf-8') # 'ws' or 'wss'
        port = etf_payload.get(b'port', 80)

        req_headers_etf = etf_payload.get(b'headers', [])
        req_headers_asgi = []
        for k_bin, v_bin in req_headers_etf:
            req_headers_asgi.append((k_bin.lower(), v_bin))

        # This is for initial connection. Subsequent messages will be handled by dedicated handlers.
        scope = {
            'type': 'websocket',
            'asgi': {'version': '3.0', 'spec_version': '2.1'},
            'http_version': '1.1', # Initial handshake is HTTP/1.1
            'scheme': scheme,
            'path': path,
            'raw_path': path.encode('latin-1'),
            'query_string': query_string.encode('latin-1'),
            'headers': req_headers_asgi,
            'server': ('omnicorn', port),
            'client': ('127.0.0.1', 0),
            'subprotocols': [], # Could be passed from Erlang if client offers them
            'state': {}, # ASGI spec defines this, but we don't manage state here
        }

        # WebSocket-specific response messages
        response_event = {} # Stores the first message from the app (accept/close)

        async def receive_websocket():
            # Initial connection always starts with a 'connect' message
            return {'type': 'websocket.connect'}

        async def send_websocket(message):
            # Store the first response message (websocket.accept or websocket.close)
            # Subsequent messages (websocket.send) are handled by a separate path
            response_event.update(message)

        try:
            await app(scope, receive_websocket, send_websocket)
        except Exception:
            sys.stderr.write(f"ASGI WebSocket App Error (handshake): {traceback.format_exc()}\n")
            response_event = {'type': 'websocket.close', 'code': 1011} # Internal Error

        # Return the handshake response to Erlang
        # Erlang expects an Erlang map with status/headers for HTTP,
        # but for WSGI, it needs a specific control message for "accept" or "close"
        if response_event.get('type') == 'websocket.accept':
            # WebSocket accepted, return a special term for Erlang
            # Subprotocols could be negotiated here.
            subprotocol = response_event.get('subprotocol')
            return {b'websocket_handshake': b'accept', b'subprotocol': erlpack.pack(subprotocol) if subprotocol else b''}
        elif response_event.get('type') == 'websocket.close':
            # WebSocket rejected/closed
            return {b'websocket_handshake': b'close', b'code': response_event.get('code', 1000)}
        else:
            return {b'websocket_handshake': b'error', b'code': 1001, b'reason': b"ASGI app sent unexpected message"}

    @staticmethod
    async def _handle_websocket_message(app, etf_payload):
        """
        Handles incoming WebSocket messages (text/binary) after the handshake.
        This will be called by Erlang for active WebSocket connections.
        """
        # WebSocket connection info (same as initial handshake scope for context)
        path = etf_payload[b'path'].decode('utf-8')
        query_string = etf_payload[b'query'].decode('utf-8')
        scheme = etf_payload.get(b'scheme', b'ws').decode('utf-8')
        port = etf_payload.get(b'port', 80)

        req_headers_etf = etf_payload.get(b'headers', [])
        req_headers_asgi = []
        for k_bin, v_bin in req_headers_etf:
            req_headers_asgi.append((k_bin.lower(), v_bin))

        message_type = etf_payload.get(b'message_type') # b'text' or b'binary'
        message_content = etf_payload.get(b'content') # binary or string

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
            'subprotocols': [],
            'state': etf_payload.get(b'connection_state', {}), # Carry state if any
            'websocket.client': etf_payload.get(b'client_info') # Client IP/Port tuple
        }

        response_messages = asyncio.Queue()

        async def receive_websocket_message():
            if message_type == b'text':
                return {'type': 'websocket.receive', 'text': message_content.decode('utf-8')}
            elif message_type == b'binary':
                return {'type': 'websocket.receive', 'bytes': message_content}
            else:
                return {'type': 'websocket.disconnect', 'code': 1000} # Default close

        async def send_websocket_message(message):
            await response_messages.put(message)

        try:
            await app(scope, receive_websocket_message, send_websocket_message)
        except Exception:
            sys.stderr.write(f"ASGI WebSocket App Error (message): {traceback.format_exc()}\n")
            await response_messages.put({'type': 'websocket.close', 'code': 1011})

        # Collect all messages sent by the ASGI app
        output_messages = []
        while not response_messages.empty():
            output_messages.append(response_messages.get_nowait())

        # Transform messages for Erlang
        erlang_responses = []
        for msg in output_messages:
            if msg['type'] == 'websocket.send':
                if 'text' in msg:
                    erlang_responses.append({b'type': b'send_text', b'content': msg['text'].encode('utf-8')})
                elif 'bytes' in msg:
                    erlang_responses.append({b'type': b'send_binary', b'content': msg['bytes']})
            elif msg['type'] == 'websocket.close':
                erlang_responses.append({b'type': b'close', b'code': msg.get('code', 1000)})

        return {b'websocket_message_response': erlang_responses, b'connection_state': scope['state']}

    @staticmethod
    async def _handle_websocket_disconnect(app, etf_payload):
        """
        Handles incoming WebSocket disconnect events.
        """
        path = etf_payload[b'path'].decode('utf-8')
        query_string = etf_payload[b'query'].decode('utf-8')
        scheme = etf_payload.get(b'scheme', b'ws').decode('utf-8')
        port = etf_payload.get(b'port', 80)

        req_headers_etf = etf_payload.get(b'headers', [])
        req_headers_asgi = []
        for k_bin, v_bin in req_headers_etf:
            req_headers_asgi.append((k_bin.lower(), v_bin))

        code = etf_payload.get(b'code', 1000)

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
            'subprotocols': [],
            'state': etf_payload.get(b'connection_state', {}),
            'websocket.client': etf_payload.get(b'client_info')
        }

        async def receive_websocket_disconnect():
            return {'type': 'websocket.disconnect', 'code': code}

        async def send_websocket_disconnect(message):
            pass # No outgoing messages expected on disconnect

        try:
            await app(scope, receive_websocket_disconnect, send_websocket_disconnect)
        except Exception:
            sys.stderr.write(f"ASGI WebSocket App Error (disconnect): {traceback.format_exc()}\n")

        return {b'websocket_disconnect_response': b'ok'}

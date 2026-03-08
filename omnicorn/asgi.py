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
        scope_type = etf_payload.get(b'scope_type', b'http').decode('utf-8')

        if scope_type == 'http':
            return await ASGIAdapter._handle_http_request(app, etf_payload)
        elif scope_type == 'websocket':
            return await ASGIAdapter._handle_websocket_request(app, etf_payload)
        else:
            sys.stderr.write(f"Unknown scope type: {scope_type}\n")
            return {b'status': 500, b'body': b"Unknown scope type"}

    @staticmethod
    def _parse_headers(etf_payload):
        # Gracefully handle `erlpack` translating Erlang cowboy header maps to dicts
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

        response_state = {
            'status': 500,
            'headers': {},
            'body': b''
        }

        input_queue = asyncio.Queue()
        await input_queue.put({'type': 'http.request', 'body': body_bytes, 'more_body': False})

        async def receive_http():
            return await input_queue.get()

        async def send_http(message):
            if message['type'] == 'http.response.start':
                response_state['status'] = message['status']
                for k_bytes, v_bytes in message.get('headers',[]):
                    # Save as mapping so Erlang resolves as map instead of crashing Cowboy iterator
                    response_state['headers'][k_bytes] = v_bytes
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

        response_event = {}

        async def receive_websocket():
            return {'type': 'websocket.connect'}

        async def send_websocket(message):
            response_event.update(message)

        try:
            await app(scope, receive_websocket, send_websocket)
        except Exception:
            sys.stderr.write(f"ASGI WebSocket App Error (handshake): {traceback.format_exc()}\n")
            response_event = {'type': 'websocket.close', 'code': 1011}

        if response_event.get('type') == 'websocket.accept':
            subprotocol = response_event.get('subprotocol', b'')
            return {b'websocket_handshake': b'accept', b'subprotocol': subprotocol}
        elif response_event.get('type') == 'websocket.close':
            return {b'websocket_handshake': b'close', b'code': response_event.get('code', 1000)}
        else:
            return {b'websocket_handshake': b'error', b'code': 1001, b'reason': b"ASGI app sent unexpected message"}

    @staticmethod
    async def _handle_websocket_message(app, etf_payload):
        path = etf_payload.get(b'path', b'/').decode('utf-8')
        query_string = etf_payload.get(b'query', b'').decode('utf-8')
        scheme = etf_payload.get(b'scheme', b'ws').decode('utf-8')
        port = etf_payload.get(b'port', 80)

        req_headers_asgi = ASGIAdapter._parse_headers(etf_payload)

        message_type = etf_payload.get(b'message_type')
        message_content = etf_payload.get(b'content')

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
            'state': etf_payload.get(b'connection_state', {}),
            'websocket.client': etf_payload.get(b'client_info')
        }

        response_messages = asyncio.Queue()

        async def receive_websocket_message():
            if message_type == b'text':
                return {'type': 'websocket.receive', 'text': message_content.decode('utf-8')}
            elif message_type == b'binary':
                return {'type': 'websocket.receive', 'bytes': message_content}
            else:
                return {'type': 'websocket.disconnect', 'code': 1000}

        async def send_websocket_message(message):
            await response_messages.put(message)

        try:
            await app(scope, receive_websocket_message, send_websocket_message)
        except Exception:
            sys.stderr.write(f"ASGI WebSocket App Error (message): {traceback.format_exc()}\n")
            await response_messages.put({'type': 'websocket.close', 'code': 1011})

        output_messages =[]
        while not response_messages.empty():
            output_messages.append(response_messages.get_nowait())

        erlang_responses =[]
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
        path = etf_payload.get(b'path', b'/').decode('utf-8')
        query_string = etf_payload.get(b'query', b'').decode('utf-8')
        scheme = etf_payload.get(b'scheme', b'ws').decode('utf-8')
        port = etf_payload.get(b'port', 80)

        req_headers_asgi = ASGIAdapter._parse_headers(etf_payload)
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
            'subprotocols':[],
            'state': etf_payload.get(b'connection_state', {}),
            'websocket.client': etf_payload.get(b'client_info')
        }

        async def receive_websocket_disconnect():
            return {'type': 'websocket.disconnect', 'code': code}

        async def send_websocket_disconnect(message):
            pass

        try:
            await app(scope, receive_websocket_disconnect, send_websocket_disconnect)
        except Exception:
            sys.stderr.write(f"ASGI WebSocket App Error (disconnect): {traceback.format_exc()}\n")

        return {b'websocket_disconnect_response': b'ok'}

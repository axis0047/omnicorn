import asyncio
import sys

class ASGIAdapter:
    @staticmethod
    def run(app, payload):
        """
        Runs an ASGI app for a single request using a transient Event Loop.
        """
        # Create a new loop for this request to ensure isolation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(ASGIAdapter._run_async(app, payload))
        finally:
            loop.close()

    @staticmethod
    async def _run_async(app, payload):
        # 1. Prepare Data
        body_str = payload.get('body', '')
        body_bytes = body_str.encode('utf-8') if isinstance(body_str, str) else body_str

        # Headers must be list of [bytes, bytes]
        headers = []
        for k, v in payload.get('headers', {}).items():
            headers.append([k.lower().encode('latin-1'), str(v).encode('latin-1')])

        # 2. Scope
        scope = {
            'type': 'http',
            'asgi': {'version': '3.0', 'spec_version': '2.1'},
            'http_version': '1.1',
            'server': ('omnicorn', payload.get('port', 80)),
            'client': ('127.0.0.1', 0),
            'scheme': payload.get('scheme', 'http'),
            'method': payload.get('method', 'GET'),
            'path': payload.get('path', '/'),
            'raw_path': payload.get('path', '/').encode('latin-1'),
            'query_string': payload.get('query', '').encode('latin-1'),
            'headers': headers,
        }

        # 3. Response State
        response_state = {
            'status': 200,
            'headers': {},
            'body': b''
        }

        # 4. Channels
        # Pre-fill receive queue with the single body chunk (non-streaming for v1)
        receive_queue = asyncio.Queue()
        await receive_queue.put({
            'type': 'http.request',
            'body': body_bytes,
            'more_body': False
        })

        async def receive():
            return await receive_queue.get()

        async def send(message):
            if message['type'] == 'http.response.start':
                response_state['status'] = message['status']
                for k, v in message.get('headers', []):
                    response_state['headers'][k.decode('latin-1')] = v.decode('latin-1')
            elif message['type'] == 'http.response.body':
                response_state['body'] += message.get('body', b'')

        # 5. Run App
        try:
            await app(scope, receive, send)
        except Exception as e:
            # Handle app crash
            response_state['status'] = 500
            response_state['body'] = f"Internal Server Error: {str(e)}".encode('utf-8')

        return {
            'status': response_state['status'],
            'headers': response_state['headers'],
            'body': response_state['body'].decode('utf-8', errors='replace')
        }

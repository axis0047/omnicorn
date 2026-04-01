"""
ASGI Adapter Test Suite
Coverage Target: 95%
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock

from omnicorn.web.asgi import ASGIAdapter, WS_CONNECTIONS


class TestASGIAdapterHTTP:
    """Test ASGI HTTP request handling"""
    
    @pytest.mark.asyncio
    async def test_handle_http_request_basic(self):
        """Test basic HTTP request handling"""
        async def app(scope, receive, send):
            await send({
                'type': 'http.response.start',
                'status': 200,
                'headers': [(b'content-type', b'text/plain')],
            })
            await send({
                'type': 'http.response.body',
                'body': b'Hello World',
            })
        
        payload = {
            b'method': b'GET',
            b'path': b'/',
            b'query': b'',
            b'port': 8080,
            b'scheme': b'http',
            b'headers': {},
            b'body': b''
        }
        
        result = await ASGIAdapter._handle_http_request(app, payload)
        
        assert result[b'status'] == 200
        assert result[b'body'] == b'Hello World'
    
    @pytest.mark.asyncio
    async def test_handle_http_request_with_body(self):
        """Test HTTP request with body"""
        async def app(scope, receive, send):
            await send({
                'type': 'http.response.start',
                'status': 200,
                'headers': [],
            })
            message = await receive()
            body = message.get('body', b'')
            await send({
                'type': 'http.response.body',
                'body': b'Echo: ' + body,
            })
        
        payload = {
            b'method': b'POST',
            b'path': b'/echo',
            b'query': b'',
            b'port': 8080,
            b'scheme': b'http',
            b'headers': {},
            b'body': b'Hello'
        }
        
        result = await ASGIAdapter._handle_http_request(app, payload)
        
        assert result[b'status'] == 200
        assert result[b'body'] == b'Echo: Hello'
    
    @pytest.mark.asyncio
    async def test_handle_http_request_with_headers(self):
        """Test HTTP request with headers"""
        async def app(scope, receive, send):
            await send({
                'type': 'http.response.start',
                'status': 200,
                'headers': [],
            })
            user_agent = 'unknown'
            # Headers preserve original case when passed as bytes
            for name, value in scope.get('headers', []):
                if name == b'User-Agent':
                    user_agent = value.decode()
            await send({
                'type': 'http.response.body',
                'body': user_agent.encode(),
            })

        payload = {
            b'method': b'GET',
            b'path': b'/',
            b'query': b'',
            b'port': 8080,
            b'scheme': b'http',
            b'headers': {b'User-Agent': b'TestAgent/1.0'},
            b'body': b''
        }

        result = await ASGIAdapter._handle_http_request(app, payload)

        assert result[b'status'] == 200
        assert result[b'body'] == b'TestAgent/1.0'
    
    @pytest.mark.asyncio
    async def test_handle_http_request_error(self):
        """Test HTTP request error handling"""
        async def app(scope, receive, send):
            raise ValueError("Test error")
        
        payload = {
            b'method': b'GET',
            b'path': b'/',
            b'query': b'',
            b'port': 8080,
            b'scheme': b'http',
            b'headers': {},
            b'body': b''
        }
        
        result = await ASGIAdapter._handle_http_request(app, payload)
        
        assert result[b'status'] == 500
    
    @pytest.mark.asyncio
    async def test_handle_http_request_query_string(self):
        """Test HTTP request with query string"""
        async def app(scope, receive, send):
            await send({
                'type': 'http.response.start',
                'status': 200,
                'headers': [],
            })
            query = scope.get('query_string', b'').decode()
            await send({
                'type': 'http.response.body',
                'body': query.encode(),
            })
        
        payload = {
            b'method': b'GET',
            b'path': b'/search',
            b'query': b'q=test&page=1',
            b'port': 8080,
            b'scheme': b'http',
            b'headers': {},
            b'body': b''
        }
        
        result = await ASGIAdapter._handle_http_request(app, payload)
        
        assert result[b'status'] == 200
        assert result[b'body'] == b'q=test&page=1'


class TestASGIAdapterWebSocket:
    """Test ASGI WebSocket handling"""
    
    @pytest.mark.asyncio
    async def test_websocket_handshake_accept(self):
        """Test WebSocket handshake accept"""
        async def app(scope, receive, send):
            await send({
                'type': 'websocket.accept',
                'subprotocol': None,
                'headers': [],
            })
        
        payload = {
            b'id': b'ws_test_1',
            b'path': b'/ws',
            b'query': b'',
            b'port': 8080,
            b'scheme': b'ws',
            b'headers': {}
        }
        
        mock_transport = AsyncMock()
        result = await ASGIAdapter._handle_websocket_handshake(app, payload, mock_transport)
        
        assert result[b'websocket_handshake'] == b'accept'
    
    @pytest.mark.asyncio
    async def test_websocket_handshake_close(self):
        """Test WebSocket handshake close"""
        async def app(scope, receive, send):
            await send({
                'type': 'websocket.close',
            })
        
        payload = {
            b'id': b'ws_test_2',
            b'path': b'/ws',
            b'query': b'',
            b'port': 8080,
            b'scheme': b'ws',
            b'headers': {}
        }
        
        mock_transport = AsyncMock()
        result = await ASGIAdapter._handle_websocket_handshake(app, payload, mock_transport)
        
        assert result[b'websocket_handshake'] == b'close'
    
    @pytest.mark.asyncio
    async def test_websocket_handshake_timeout(self):
        """Test WebSocket handshake timeout"""
        async def app(scope, receive, send):
            await asyncio.sleep(10)  # Never accepts
        
        payload = {
            b'id': b'ws_test_3',
            b'path': b'/ws',
            b'query': b'',
            b'port': 8080,
            b'scheme': b'ws',
            b'headers': {}
        }
        
        mock_transport = AsyncMock()
        result = await ASGIAdapter._handle_websocket_handshake(app, payload, mock_transport)
        
        assert result[b'websocket_handshake'] == b'timeout'
    
    @pytest.mark.asyncio
    async def test_websocket_message_text(self):
        """Test WebSocket text message handling"""
        async def app(scope, receive, send):
            await send({
                'type': 'websocket.accept',
            })
            message = await receive()
            # Echo back
            if message['type'] == 'websocket.receive':
                await send({
                    'type': 'websocket.send',
                    'text': message['text'],
                })
        
        payload = {
            b'id': b'ws_msg_1',
            b'message_type': b'text',
            b'content': b'Hello'
        }
        
        # First do handshake
        handshake_payload = {
            b'id': b'ws_msg_1',
            b'path': b'/ws',
            b'query': b'',
            b'port': 8080,
            b'scheme': b'ws',
            b'headers': {}
        }
        
        mock_transport = AsyncMock()
        await ASGIAdapter._handle_websocket_handshake(app, handshake_payload, mock_transport)
        
        # Then send message
        await ASGIAdapter._handle_websocket_message(app, payload)
        
        assert b'ws_msg_1' in WS_CONNECTIONS
        del WS_CONNECTIONS[b'ws_msg_1']
    
    @pytest.mark.asyncio
    async def test_websocket_message_binary(self):
        """Test WebSocket binary message handling"""
        payload = {
            b'id': b'ws_msg_2',
            b'message_type': b'binary',
            b'content': b'\x00\x01\x02'
        }
        
        # Mock connection exists
        WS_CONNECTIONS[b'ws_msg_2'] = {
            'rq': asyncio.Queue(),
            'task': asyncio.create_task(asyncio.sleep(10))
        }
        
        async def app(scope, receive, send):
            pass
        
        await ASGIAdapter._handle_websocket_message(app, payload)
        
        # Cleanup
        if b'ws_msg_2' in WS_CONNECTIONS:
            WS_CONNECTIONS[b'ws_msg_2']['task'].cancel()
            del WS_CONNECTIONS[b'ws_msg_2']
    
    @pytest.mark.asyncio
    async def test_websocket_disconnect(self):
        """Test WebSocket disconnect handling"""
        async def app(scope, receive, send):
            await send({
                'type': 'websocket.accept',
            })
            message = await receive()
            if message['type'] == 'websocket.disconnect':
                pass
        
        # First do handshake
        handshake_payload = {
            b'id': b'ws_disc_1',
            b'path': b'/ws',
            b'query': b'',
            b'port': 8080,
            b'scheme': b'ws',
            b'headers': {}
        }
        
        mock_transport = AsyncMock()
        await ASGIAdapter._handle_websocket_handshake(app, handshake_payload, mock_transport)
        
        # Then disconnect
        disconnect_payload = {
            b'id': b'ws_disc_1'
        }
        
        await ASGIAdapter._handle_websocket_disconnect(app, disconnect_payload)
        
        assert b'ws_disc_1' not in WS_CONNECTIONS


class TestASGIAdapterHelpers:
    """Test ASGI adapter helper functions"""
    
    def test_parse_headers_dict(self):
        """Test parsing headers from dict"""
        payload = {
            b'headers': {
                b'Content-Type': b'application/json',
                b'User-Agent': b'TestAgent'
            }
        }
        
        headers = ASGIAdapter._parse_headers(payload)
        
        assert len(headers) == 2
        # Headers preserve case when bytes
        assert (b'Content-Type', b'application/json') in headers
    
    def test_parse_headers_list(self):
        """Test parsing headers from list"""
        payload = {
            b'headers': [
                (b'Content-Type', b'application/json'),
                (b'User-Agent', b'TestAgent')
            ]
        }
        
        headers = ASGIAdapter._parse_headers(payload)
        
        assert len(headers) == 2
    
    def test_parse_headers_empty(self):
        """Test parsing empty headers"""
        payload = {b'headers': {}}
        
        headers = ASGIAdapter._parse_headers(payload)
        
        assert headers == []

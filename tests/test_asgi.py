"""
Tests for Omnicorn ASGI adapter.
"""

import pytest
from omnicorn.web.asgi import ASGIAdapter


@pytest.mark.asyncio
async def test_asgi_adapter_http_basic():
    """Test basic ASGI HTTP request handling."""
    
    async def simple_app(scope, receive, send):
        assert scope['type'] == 'http'
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
    
    result = await ASGIAdapter._handle_http_request(simple_app, payload)
    
    assert result[b'status'] == 200
    assert result[b'body'] == b'Hello World'


@pytest.mark.asyncio
async def test_asgi_adapter_http_with_body():
    """Test ASGI HTTP request with body."""
    
    async def echo_app(scope, receive, send):
        await send({
            'type': 'http.response.start',
            'status': 200,
            'headers': [(b'content-type', b'text/plain')],
        })
        
        # Get the request body from receive
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
        b'body': b'Hello ASGI'
    }
    
    result = await ASGIAdapter._handle_http_request(echo_app, payload)
    
    assert result[b'status'] == 200
    assert result[b'body'] == b'Echo: Hello ASGI'


@pytest.mark.asyncio
async def test_asgi_adapter_headers():
    """Test ASGI header handling."""
    
    async def header_app(scope, receive, send):
        # Find user-agent header
        headers = scope.get('headers', [])
        user_agent = b'unknown'
        for name, value in headers:
            if name == b'user-agent':
                user_agent = value
                break
        
        await send({
            'type': 'http.response.start',
            'status': 200,
            'headers': [(b'content-type', b'text/plain')],
        })
        await send({
            'type': 'http.response.body',
            'body': user_agent,
        })
    
    payload = {
        b'method': b'GET',
        b'path': b'/headers',
        b'query': b'',
        b'port': 8080,
        b'scheme': b'http',
        b'headers': {b'User-Agent': b'TestASGI/1.0'},
        b'body': b''
    }
    
    result = await ASGIAdapter._handle_http_request(header_app, payload)
    
    assert result[b'status'] == 200
    assert result[b'body'] == b'TestASGI/1.0'


@pytest.mark.asyncio
async def test_asgi_adapter_websocket_handshake():
    """Test ASGI WebSocket handshake."""
    
    async def ws_app(scope, receive, send):
        assert scope['type'] == 'websocket'
        # Accept the connection
        await send({
            'type': 'websocket.accept',
            'subprotocol': None,
            'headers': [],
        })
    
    payload = {
        b'id': b'ws_test_123',
        b'path': b'/ws',
        b'query': b'',
        b'port': 8080,
        b'scheme': b'ws',
        b'headers': {}
    }
    
    # Mock transport
    class MockTransport:
        def __init__(self):
            self.sent = []
        
        async def send(self, msg):
            self.sent.append(msg)
    
    transport = MockTransport()
    
    result = await ASGIAdapter._handle_websocket_handshake(ws_app, payload, transport)
    
    # Should accept handshake
    assert result[b'websocket_handshake'] == b'accept'


@pytest.mark.asyncio
async def test_asgi_adapter_websocket_message():
    """Test ASGI WebSocket message handling."""
    
    received_messages = []
    
    async def echo_ws_app(scope, receive, send):
        # Accept connection
        await send({
            'type': 'websocket.accept',
            'subprotocol': None,
            'headers': [],
        })
        
        # Receive and echo messages
        while True:
            message = await receive()
            if message['type'] == 'websocket.receive':
                received_messages.append(message)
                # Echo back
                if 'text' in message:
                    await send({
                        'type': 'websocket.send',
                        'text': message['text'],
                    })
                elif 'bytes' in message:
                    await send({
                        'type': 'websocket.send',
                        'bytes': message['bytes'],
                    })
            elif message['type'] == 'websocket.disconnect':
                break
    
    # Mock transport for handshake
    class MockTransport:
        def __init__(self):
            self.sent = []
        
        async def send(self, msg):
            self.sent.append(msg)
    
    transport = MockTransport()
    
    payload_handshake = {
        b'id': b'ws_msg_test',
        b'path': b'/ws',
        b'query': b'',
        b'port': 8080,
        b'scheme': b'ws',
        b'headers': {}
    }
    
    # Do handshake first
    await ASGIAdapter._handle_websocket_handshake(echo_ws_app, payload_handshake, transport)
    
    # Send a message
    payload_message = {
        b'id': b'ws_msg_test',
        b'message_type': b'text',
        b'content': b'Hello WebSocket'
    }
    
    await ASGIAdapter._handle_websocket_message(echo_ws_app, payload_message)
    
    # Verify message was received
    assert len(received_messages) == 1
    assert received_messages[0]['type'] == 'websocket.receive'
    assert received_messages[0]['text'] == 'Hello WebSocket'


@pytest.mark.asyncio
async def test_asgi_adapter_websocket_disconnect():
    """Test ASGI WebSocket disconnect handling."""
    
    disconnected = False
    
    async def ws_app(scope, receive, send):
        nonlocal disconnected
        await send({
            'type': 'websocket.accept',
            'subprotocol': None,
            'headers': [],
        })
        
        message = await receive()
        if message['type'] == 'websocket.disconnect':
            disconnected = True
    
    # Mock transport
    class MockTransport:
        async def send(self, msg):
            pass
    
    # Do handshake
    payload_handshake = {
        b'id': b'ws_disc_test',
        b'path': b'/ws',
        b'query': b'',
        b'port': 8080,
        b'scheme': b'ws',
        b'headers': {}
    }
    
    await ASGIAdapter._handle_websocket_handshake(ws_app, payload_handshake, MockTransport())
    
    # Disconnect
    payload_disconnect = {
        b'id': b'ws_disc_test'
    }
    
    await ASGIAdapter._handle_websocket_disconnect(ws_app, payload_disconnect)
    
    # Verify disconnect was handled
    assert disconnected


@pytest.mark.asyncio
async def test_asgi_adapter_error_handling():
    """Test ASGI error handling."""
    
    async def error_app(scope, receive, send):
        raise ValueError("Test error")
    
    payload = {
        b'method': b'GET',
        b'path': b'/error',
        b'query': b'',
        b'port': 8080,
        b'scheme': b'http',
        b'headers': {},
        b'body': b''
    }
    
    result = await ASGIAdapter._handle_http_request(error_app, payload)
    
    # Should return 500 on error
    assert result[b'status'] == 500

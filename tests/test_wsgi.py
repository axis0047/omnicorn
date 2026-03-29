"""
Tests for Omnicorn WSGI adapter.
"""

import pytest
from omnicorn.web.wsgi import WSGIAdapter


def test_wsgi_adapter_basic():
    """Test basic WSGI request handling."""
    
    def simple_app(environ, start_response):
        status = '200 OK'
        headers = [('Content-Type', 'text/plain')]
        start_response(status, headers)
        return [b'Hello World']
    
    payload = {
        b'method': b'GET',
        b'path': b'/',
        b'query': b'',
        b'port': 8080,
        b'scheme': b'http',
        b'headers': {},
        b'body': b''
    }
    
    result = WSGIAdapter.run(simple_app, payload)
    
    assert result[b'status'] == 200
    assert result[b'body'] == b'Hello World'
    assert b'Content-Type' in result[b'headers']


def test_wsgi_adapter_with_body():
    """Test WSGI request with body."""
    
    def echo_app(environ, start_response):
        from io import BytesIO
        status = '200 OK'
        headers = [('Content-Type', 'text/plain')]
        start_response(status, headers)
        
        # Read body from wsgi.input
        content_length = int(environ.get('CONTENT_LENGTH', 0))
        body = environ['wsgi.input'].read(content_length)
        return [b'Echo: ' + body]
    
    payload = {
        b'method': b'POST',
        b'path': b'/echo',
        b'query': b'',
        b'port': 8080,
        b'scheme': b'http',
        b'headers': {b'Content-Type': b'text/plain'},
        b'body': b'Hello Omnicorn'
    }
    
    result = WSGIAdapter.run(echo_app, payload)
    
    assert result[b'status'] == 200
    assert result[b'body'] == b'Echo: Hello Omnicorn'


def test_wsgi_adapter_headers():
    """Test WSGI header handling."""
    
    def header_app(environ, start_response):
        status = '200 OK'
        headers = [('Content-Type', 'application/json')]
        start_response(status, headers)
        
        # Return a header from the request
        user_agent = environ.get('HTTP_USER_AGENT', 'unknown')
        return [user_agent.encode()]
    
    payload = {
        b'method': b'GET',
        b'path': b'/headers',
        b'query': b'',
        b'port': 8080,
        b'scheme': b'http',
        b'headers': {b'User-Agent': b'TestAgent/1.0'},
        b'body': b''
    }
    
    result = WSGIAdapter.run(header_app, payload)
    
    assert result[b'status'] == 200
    assert result[b'body'] == b'TestAgent/1.0'


def test_wsgi_adapter_query_string():
    """Test WSGI query string handling."""
    
    def query_app(environ, start_response):
        status = '200 OK'
        headers = [('Content-Type', 'text/plain')]
        start_response(status, headers)
        
        query_string = environ.get('QUERY_STRING', '')
        return [f'Query: {query_string}'.encode()]
    
    payload = {
        b'method': b'GET',
        b'path': b'/search',
        b'query': b'q=test&page=1',
        b'port': 8080,
        b'scheme': b'http',
        b'headers': {},
        b'body': b''
    }
    
    result = WSGIAdapter.run(query_app, payload)
    
    assert result[b'status'] == 200
    assert result[b'body'] == b'Query: q=test&page=1'


def test_wsgi_adapter_error_status():
    """Test WSGI error status handling."""
    
    def error_app(environ, start_response):
        status = '500 Internal Server Error'
        headers = [('Content-Type', 'text/plain')]
        start_response(status, headers)
        return [b'Error']
    
    payload = {
        b'method': b'GET',
        b'path': b'/error',
        b'query': b'',
        b'port': 8080,
        b'scheme': b'http',
        b'headers': {},
        b'body': b''
    }
    
    result = WSGIAdapter.run(error_app, payload)
    
    assert result[b'status'] == 500


def test_wsgi_adapter_empty_body():
    """Test WSGI with empty body."""
    
    def empty_app(environ, start_response):
        status = '204 No Content'
        headers = []
        start_response(status, headers)
        return []
    
    payload = {
        b'method': b'GET',
        b'path': b'/empty',
        b'query': b'',
        b'port': 8080,
        b'scheme': b'http',
        b'headers': {},
        b'body': b''
    }
    
    result = WSGIAdapter.run(empty_app, payload)
    
    assert result[b'status'] == 204
    assert result[b'body'] == b''

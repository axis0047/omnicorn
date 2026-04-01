"""
WSGI Adapter Test Suite
Coverage Target: 95%
"""

import io
from omnicorn.web.wsgi import WSGIAdapter


class TestWSGIAdapter:
    """Test WSGI adapter"""
    
    def test_wsgi_basic_request(self):
        """Test basic WSGI request"""
        def app(environ, start_response):
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
        
        result = WSGIAdapter.run(app, payload)
        
        assert result[b'status'] == 200
        assert result[b'body'] == b'Hello World'
    
    def test_wsgi_request_with_body(self):
        """Test WSGI request with body"""
        def app(environ, start_response):
            status = '200 OK'
            headers = [('Content-Type', 'text/plain')]
            start_response(status, headers)
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
            b'body': b'Hello'
        }
        
        result = WSGIAdapter.run(app, payload)
        
        assert result[b'status'] == 200
        assert result[b'body'] == b'Echo: Hello'
    
    def test_wsgi_request_with_headers(self):
        """Test WSGI request with headers"""
        def app(environ, start_response):
            status = '200 OK'
            headers = [('Content-Type', 'text/plain')]
            start_response(status, headers)
            user_agent = environ.get('HTTP_USER_AGENT', 'unknown')
            return [user_agent.encode()]
        
        payload = {
            b'method': b'GET',
            b'path': b'/',
            b'query': b'',
            b'port': 8080,
            b'scheme': b'http',
            b'headers': {b'User-Agent': b'TestAgent/1.0'},
            b'body': b''
        }
        
        result = WSGIAdapter.run(app, payload)
        
        assert result[b'status'] == 200
        assert result[b'body'] == b'TestAgent/1.0'
    
    def test_wsgi_request_with_query_string(self):
        """Test WSGI request with query string"""
        def app(environ, start_response):
            status = '200 OK'
            headers = [('Content-Type', 'text/plain')]
            start_response(status, headers)
            query_string = environ.get('QUERY_STRING', '')
            return [query_string.encode()]
        
        payload = {
            b'method': b'GET',
            b'path': b'/search',
            b'query': b'q=test&page=1',
            b'port': 8080,
            b'scheme': b'http',
            b'headers': {},
            b'body': b''
        }
        
        result = WSGIAdapter.run(app, payload)
        
        assert result[b'status'] == 200
        assert result[b'body'] == b'q=test&page=1'
    
    def test_wsgi_error_status(self):
        """Test WSGI error status"""
        def app(environ, start_response):
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
        
        result = WSGIAdapter.run(app, payload)
        
        assert result[b'status'] == 500
    
    def test_wsgi_empty_body(self):
        """Test WSGI with empty body"""
        def app(environ, start_response):
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
        
        result = WSGIAdapter.run(app, payload)
        
        assert result[b'status'] == 204
        assert result[b'body'] == b''
    
    def test_wsgi_environ_values(self):
        """Test WSGI environ values are correct"""
        def app(environ, start_response):
            status = '200 OK'
            headers = []
            start_response(status, headers)
            
            assert environ['wsgi.version'] == (1, 0)
            assert environ['wsgi.url_scheme'] == 'http'
            assert environ['REQUEST_METHOD'] == 'GET'
            assert environ['PATH_INFO'] == '/test'
            assert environ['SERVER_PORT'] == '8080'
            
            return [b'OK']
        
        payload = {
            b'method': b'GET',
            b'path': b'/test',
            b'query': b'',
            b'port': 8080,
            b'scheme': b'http',
            b'headers': {},
            b'body': b''
        }
        
        result = WSGIAdapter.run(app, payload)
        
        assert result[b'status'] == 200
    
    def test_wsgi_start_response(self):
        """Test start_response is called correctly"""
        def app(environ, start_response):
            status = '201 Created'
            headers = [
                ('Content-Type', 'application/json'),
                ('X-Custom', 'value')
            ]
            start_response(status, headers)
            return [b'{}']
        
        payload = {
            b'method': b'POST',
            b'path': b'/api',
            b'query': b'',
            b'port': 8080,
            b'scheme': b'http',
            b'headers': {},
            b'body': b''
        }
        
        result = WSGIAdapter.run(app, payload)
        
        assert result[b'status'] == 201
        assert b'Content-Type' in result[b'headers']
    
    def test_wsgi_body_as_string(self):
        """Test WSGI handles body as string"""
        def app(environ, start_response):
            status = '200 OK'
            headers = []
            start_response(status, headers)
            return [b'OK']
        
        payload = {
            b'method': b'POST',
            b'path': b'/',
            b'query': b'',
            b'port': 8080,
            b'scheme': b'http',
            b'headers': {},
            b'body': 'string body'  # String instead of bytes
        }
        
        result = WSGIAdapter.run(app, payload)
        
        assert result[b'status'] == 200
    
    def test_wsgi_iterator_close(self):
        """Test WSGI iterator close is called"""
        closed = [False]
        
        class TestIterator:
            def __init__(self):
                self.data = [b'chunk1', b'chunk2']
                self.index = 0
            
            def __iter__(self):
                return self
            
            def __next__(self):
                if self.index >= len(self.data):
                    raise StopIteration
                chunk = self.data[self.index]
                self.index += 1
                return chunk
            
            def close(self):
                closed[0] = True
        
        def app(environ, start_response):
            status = '200 OK'
            headers = []
            start_response(status, headers)
            return TestIterator()
        
        payload = {
            b'method': b'GET',
            b'path': b'/',
            b'query': b'',
            b'port': 8080,
            b'scheme': b'http',
            b'headers': {},
            b'body': b''
        }
        
        result = WSGIAdapter.run(app, payload)
        
        assert result[b'status'] == 200
        assert closed[0] is True

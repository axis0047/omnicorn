import io
import sys

class WSGIAdapter:
    @staticmethod
    def run(app, payload):
        """
        Translates Omnicorn JSON payload to WSGI Environ and runs the app.
        """
        # 1. Decode Body
        body_str = payload.get('body', '')
        if isinstance(body_str, str):
            body_bytes = body_str.encode('utf-8')
        else:
            body_bytes = body_str

        # 2. Construct WSGI Environ
        environ = {
            'wsgi.version': (1, 0),
            'wsgi.url_scheme': payload.get('scheme', 'http'),
            'wsgi.input': io.BytesIO(body_bytes),
            'wsgi.errors': sys.stderr,
            'wsgi.multithread': False,
            'wsgi.multiprocess': True,
            'wsgi.run_once': False,
            'REQUEST_METHOD': payload.get('method', 'GET'),
            'SCRIPT_NAME': '',
            'PATH_INFO': payload.get('path', '/'),
            'QUERY_STRING': payload.get('query', ''),
            'SERVER_NAME': 'omnicorn',
            'SERVER_PORT': str(payload.get('port', 80)),
            'SERVER_PROTOCOL': 'HTTP/1.1',
        }

        content_length = str(len(body_bytes))
        environ['CONTENT_LENGTH'] = content_length

        # 3. Process Headers
        # HTTP_ variables, Content-Type, Content-Length
        req_headers = payload.get('headers', {})
        for k, v in req_headers.items():
            key = k.upper().replace('-', '_')
            if key == 'CONTENT_TYPE':
                environ['CONTENT_TYPE'] = v
            elif key == 'CONTENT_LENGTH':
                continue # handled above
            else:
                environ[f'HTTP_{key}'] = v

        # 4. Response Collector
        response = {
            'status': 500,
            'headers': {},
            'body': []
        }

        def start_response(status, headers, exc_info=None):
            if exc_info:
                try:
                    if response['headers']:
                        raise exc_info[1].with_traceback(exc_info[2])
                finally:
                    exc_info = None

            try:
                code = int(status.split(' ')[0])
            except (ValueError, IndexError):
                code = 500

            response['status'] = code
            # Convert list of tuples to dict for JSON transfer
            # (In production, use list of lists to support duplicate headers)
            for k, v in headers:
                response['headers'][k] = v

            return response['body'].append

        # 5. Execute App
        result = app(environ, start_response)
        try:
            for data in result:
                response['body'].append(data)
        finally:
            if hasattr(result, 'close'):
                result.close()

        # 6. Finalize
        full_body = b''.join(response['body'])

        return {
            'status': response['status'],
            'headers': response['headers'],
            'body': full_body.decode('utf-8', errors='replace')
        }

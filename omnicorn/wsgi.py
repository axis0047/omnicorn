import io
import sys

class WSGIAdapter:
    @staticmethod
    def run(app, payload):
        """
        Translates Omnicorn ETF payload to WSGI Environ and runs the app.
        """
        # 1. Decode Body
        body_str = payload.get(b'body', b'')
        if isinstance(body_str, str):
            body_bytes = body_str.encode('utf-8')
        else:
            body_bytes = body_str

        # 2. Construct WSGI Environ using byte keys
        environ = {
            'wsgi.version': (1, 0),
            'wsgi.url_scheme': payload.get(b'scheme', b'http').decode('utf-8'),
            'wsgi.input': io.BytesIO(body_bytes),
            'wsgi.errors': sys.stderr,
            'wsgi.multithread': False,
            'wsgi.multiprocess': True,
            'wsgi.run_once': False,
            'REQUEST_METHOD': payload.get(b'method', b'GET').decode('utf-8'),
            'SCRIPT_NAME': '',
            'PATH_INFO': payload.get(b'path', b'/').decode('utf-8'),
            'QUERY_STRING': payload.get(b'query', b'').decode('utf-8'),
            'SERVER_NAME': 'omnicorn',
            'SERVER_PORT': str(payload.get(b'port', 80)),
            'SERVER_PROTOCOL': 'HTTP/1.1',
        }

        content_length = str(len(body_bytes))
        environ['CONTENT_LENGTH'] = content_length

        # 3. Process Headers - Safely iterate dicts translated from Erlang Maps
        req_headers = payload.get(b'headers', {})
        header_items = req_headers.items() if isinstance(req_headers, dict) else req_headers
        for k, v in header_items:
            if isinstance(k, bytes): k = k.decode('utf-8')
            if isinstance(v, bytes): v = v.decode('utf-8')

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
            'body':[]
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

        # Maps headers back into dictionary with bytes format to prevent Cowboy looping crashes
        return {
            b'status': response['status'],
            b'headers': {
                k.encode('utf-8') if isinstance(k, str) else k:
                v.encode('utf-8') if isinstance(v, str) else v
                for k, v in response['headers'].items()
            },
            b'body': full_body
        }

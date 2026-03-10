import io
import sys


class WSGIAdapter:
    @staticmethod
    def run(app, payload):
        body_bytes = payload.get(b"body", b"")
        if isinstance(body_bytes, str):
            body_bytes = body_bytes.encode("utf-8")
        environ = {
            "wsgi.version": (1, 0),
            "wsgi.url_scheme": payload.get(b"scheme", b"http").decode("utf-8"),
            "wsgi.input": io.BytesIO(body_bytes),
            "wsgi.errors": sys.stderr,
            "wsgi.multithread": True,
            "wsgi.multiprocess": True,
            "wsgi.run_once": False,
            "REQUEST_METHOD": payload.get(b"method", b"GET").decode("utf-8"),
            "SCRIPT_NAME": "",
            "PATH_INFO": payload.get(b"path", b"/").decode("utf-8"),
            "QUERY_STRING": payload.get(b"query", b"").decode("utf-8"),
            "SERVER_NAME": "omnicorn",
            "SERVER_PORT": str(payload.get(b"port", 80)),
            "SERVER_PROTOCOL": "HTTP/1.1",
        }
        environ["CONTENT_LENGTH"] = str(len(body_bytes))
        headers = payload.get(b"headers", {})
        header_items = headers.items() if isinstance(headers, dict) else headers
        for k, v in header_items:
            key = (
                (k.decode("utf-8") if isinstance(k, bytes) else str(k))
                .upper()
                .replace("-", "_")
            )
            val = v.decode("utf-8") if isinstance(v, bytes) else str(v)
            if key == "CONTENT_TYPE":
                environ["CONTENT_TYPE"] = val
            elif key != "CONTENT_LENGTH":
                environ[f"HTTP_{key}"] = val

        response = {"status": 500, "headers": {}, "body": []}

        def start_response(status, headers, exc_info=None):
            response["status"] = int(status.split(" ")[0])
            for k, v in headers:
                response["headers"][k.encode("utf-8")] = v.encode("utf-8")
            return response["body"].append

        result = app(environ, start_response)
        try:
            for data in result:
                response["body"].append(data)
        finally:
            if hasattr(result, "close"):
                result.close()

        return {
            b"status": response["status"],
            b"headers": response["headers"],
            b"body": b"".join(response["body"]),
        }

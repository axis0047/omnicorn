import sys
import os
import importlib
import traceback
import inspect
import socket
import signal
import erlpack

from .protocol import Protocol
from .wsgi import WSGIAdapter
from .asgi import ASGIAdapter
from .core import get_task # Assuming you'll add RPC toolkit later

class OmniWorker:
    def __init__(self, app_path):
        self.app = self.load_app(app_path)

        if inspect.iscoroutinefunction(self.app) or hasattr(self.app, '__await__'):
            self.app_type = b'asgi'
        else:
            self.app_type = b'wsgi'

        self.sock_path_var = os.environ.get("OMNICORN_SOCK")
        self.sock_path = tuple(self.sock_path_var.split(":"))
        if not self.sock_path_var:
            sys.stderr.write("🔥 OMNICORN_SOCK env var missing. Cannot connect to control plane.\n")
            sys.exit(1)

    def load_app(self, path):
        try:
            if ":" not in path:
                raise ValueError("App path must be 'module:variable'")
            mod_name, var_name = path.split(":")
            mod = importlib.import_module(mod_name)
            return getattr(mod, var_name)
        except Exception:
            sys.stderr.write(f"🔥 Failed to load app: {path}\n")
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)

    def run(self):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(self.sock_path)
        except Exception as e:
            sys.stderr.write(f"🔥 Could not connect to UDS {self.sock_path}: {e}\n")
            sys.exit(1)

        Protocol.write(sock, {
            b'status': b'ready',
            b'pid': os.getpid(),
            b'type': self.app_type
        })

        while True:
            msg = Protocol.read(sock)

            if msg is None:
                break

            req_id = msg.get(b'id')
            msg_type = msg.get(b'type')
            payload = msg.get(b'payload', {})

            response_data = {}

            try:
                if msg_type == b'http':
                    if self.app_type == b'asgi':
                        # HTTP requests for ASGI apps still go through ASGIAdapter's HTTP handler
                        response_data = ASGIAdapter._handle_http_request(self.app, payload)
                    else:
                        response_data = WSGIAdapter.run(self.app, payload)

                elif msg_type == b'websocket_handshake': # New type for WS handshake
                    if self.app_type == b'asgi':
                        response_data = ASGIAdapter._handle_websocket_request(self.app, payload)
                    else:
                        response_data = {b'status': 500, b'body': b"WSGI app cannot handle WebSocket handshake"}

                elif msg_type == b'websocket_message': # New type for WS messages
                    if self.app_type == b'asgi':
                        response_data = ASGIAdapter._handle_websocket_message(self.app, payload)
                    else:
                        response_data = {b'status': 500, b'body': b"WSGI app cannot handle WebSocket messages"}

                elif msg_type == b'websocket_disconnect': # New type for WS disconnect
                    if self.app_type == b'asgi':
                        response_data = ASGIAdapter._handle_websocket_disconnect(self.app, payload)
                    else:
                        response_data = {b'status': 500, b'body': b"WSGI app cannot handle WebSocket disconnect"}

                elif msg_type == b'rpc': # RPC calls (for future toolkit)
                    func_name = payload.get(b'func').decode('utf-8')
                    args_etf = payload.get(b'args', [])
                    args = [x.decode('utf-8') if isinstance(x, bytes) else x for x in args_etf]

                    func = get_task(func_name)
                    if func:
                        result = func(*args)
                        response_data = {b'status': 200, b'result': erlpack.pack(result)}
                    else:
                        response_data = {b'status': 404, b'error': b'Function not found'}

                Protocol.write(sock, {
                    b'id': req_id,
                    b'data': response_data
                })

            except Exception:
                err_msg = traceback.format_exc()
                sys.stderr.write(f"Worker Exception request_id={req_id}:\n{err_msg}")

                Protocol.write(sock, {
                    b'id': req_id,
                    b'data': {
                        b'status': 500,
                        b'headers': [{b'content-type', b'text/plain'}],
                        b'body': b"Internal Worker Error"
                    }
                })

        sock.close()

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
    if len(sys.argv) < 2:
        sys.stderr.write("Usage: python -m omnicorn.worker <module:app>\n")
        sys.exit(1)

    worker = OmniWorker(sys.argv[1])
    worker.run()

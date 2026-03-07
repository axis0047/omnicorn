import sys
import os
import importlib
import traceback
import inspect
import socket
import signal

from .protocol import Protocol
from .wsgi import WSGIAdapter
from .asgi import ASGIAdapter
from .core import get_task

class OmniWorker:
    def __init__(self, app_path):
        self.app = self.load_app(app_path)

        if inspect.iscoroutinefunction(self.app) or hasattr(self.app, '__await__'):
            self.app_type = 'asgi'
        else:
            self.app_type = 'wsgi'

        # Connect to the High-Speed UDS provided by Erlang
        self.sock_path = os.environ.get("OMNICORN_SOCK")
        if not self.sock_path:
            raise ValueError("OMNICORN_SOCK env var missing. Cannot connect to control plane.")

    def load_app(self, path):
        try:
            if ":" not in path:
                raise ValueError("App path must be 'module:variable'")
            mod_name, var_name = path.split(":")
            mod = importlib.import_module(mod_name)
            return getattr(mod, var_name)
        except Exception:
            # Print to stderr, which Erlang now logs correctly without crashing!
            sys.stderr.write(f"🔥 Failed to load app: {path}\n")
            traceback.print_exc()
            sys.exit(1)

    def run(self):
        # 1. Establish Data Plane Connection
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(self.sock_path)
        except Exception as e:
            sys.stderr.write(f"🔥 Could not connect to UDS {self.sock_path}: {e}\n")
            sys.exit(1)

        # 2. Handshake
        Protocol.write(sock, {
            "status": "ready",
            "pid": os.getpid(),
            "type": self.app_type
        })

        # 3. Event Loop
        while True:
            msg = Protocol.read(sock)

            if msg is None:
                break # Parent closed socket

            req_id = msg.get('id')
            msg_type = msg.get('type')
            payload = msg.get('payload', {})

            response_data = {}

            try:
                if msg_type == 'http':
                    if self.app_type == 'asgi':
                        response_data = ASGIAdapter.run(self.app, payload)
                    else:
                        response_data = WSGIAdapter.run(self.app, payload)

                elif msg_type == 'rpc':
                    func_name = payload.get('func')
                    args = payload.get('args', [])
                    func = get_task(func_name)
                    if func:
                        res = func(*args)
                        response_data = {'status': 200, 'result': res}
                    else:
                        response_data = {'status': 404, 'error': 'Function not found'}

                Protocol.write(sock, {
                    'id': req_id,
                    'data': response_data
                })

            except Exception:
                err_msg = traceback.format_exc()
                # Safe logging to stderr
                sys.stderr.write(f"Worker Exception request_id={req_id}:\n{err_msg}")

                Protocol.write(sock, {
                    'id': req_id,
                    'data': {
                        'status': 500,
                        'headers': {'content-type': 'text/plain'},
                        'body': "Internal Worker Error"
                    }
                })

        sock.close()

if __name__ == "__main__":
    # Handle SIGTERM gracefully
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))

    if len(sys.argv) < 2:
        print("Usage: python -m omnicorn.worker <module:app>")
        sys.exit(1)

    OmniWorker(sys.argv[1]).run()

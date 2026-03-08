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

class OmniWorker:
    def __init__(self, app_path):
        self.app = self.load_app(app_path)

        if inspect.iscoroutinefunction(self.app) or hasattr(self.app, '__await__'):
            self.app_type = b'asgi'
        else:
            self.app_type = b'wsgi'

        self.sock_path = os.environ.get("OMNICORN_SOCK")
        if not self.sock_path:
            sys.stderr.write("🔥 OMNICORN_SOCK env var missing.\n")
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
            if msg is None: break

            req_id = msg.get(b'id')
            msg_type = msg.get(b'type')
            payload = msg.get(b'payload', {})

            try:
                # Radically simplified. ASGI handles all phases, WSGI handles only HTTP.
                if self.app_type == b'asgi':
                    response_data = ASGIAdapter.run_phase(self.app, msg_type, payload)
                else:
                    if msg_type == b'http':
                        response_data = WSGIAdapter.run(self.app, payload)
                    else:
                        response_data = {b'status': 500, b'body': b"WSGI app cannot handle WebSockets"}

                Protocol.write(sock, {b'id': req_id, b'data': response_data})

            except Exception:
                err = traceback.format_exc()
                sys.stderr.write(f"Worker Error: {err}\n")
                Protocol.write(sock, {
                    b'id': req_id,
                    b'data': {b'status': 500, b'body': b"Internal Worker Error"}
                })

        sock.close()

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
    OmniWorker(sys.argv[1]).run()

import sys
import os
import importlib
import traceback
import inspect
import asyncio

from .protocol import Protocol
from .wsgi import WSGIAdapter
from .asgi import ASGIAdapter
from .core import get_task

class OmniWorker:
    def __init__(self, app_path):
        self.app = self.load_app(app_path)

        # Detect App Type
        if inspect.iscoroutinefunction(self.app) or hasattr(self.app, '__await__'):
            self.app_type = 'asgi'
        else:
            self.app_type = 'wsgi'

        self.stdin = sys.stdin.buffer
        self.stdout = sys.stdout.buffer

    def load_app(self, path):
        try:
            if ":" not in path:
                raise ValueError("App path must be 'module:variable'")
            mod_name, var_name = path.split(":")
            mod = importlib.import_module(mod_name)
            return getattr(mod, var_name)
        except Exception:
            sys.stderr.write(f"Failed to load app: {path}\n")
            traceback.print_exc()
            sys.exit(1)

    def run(self):
        # 1. Handshake
        Protocol.write(self.stdout, {
            "status": "ready",
            "pid": os.getpid(),
            "type": self.app_type
        })

        # 2. Event Loop
        while True:
            # Blocking Read
            msg = Protocol.read(self.stdin)

            if msg is None:
                # Pipe closed by Erlang, exit gracefully
                break

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

                else:
                    response_data = {'error': 'Unknown message type'}

                # Send Response
                Protocol.write(self.stdout, {
                    'id': req_id,
                    'data': response_data
                })

            except Exception:
                # Catch-all for app errors to prevent worker death
                # Let Erlang decide if it wants to kill us (via 500 status logic or timeout)
                err_msg = traceback.format_exc()
                sys.stderr.write(err_msg)

                Protocol.write(self.stdout, {
                    'id': req_id,
                    'data': {
                        'status': 500,
                        'headers': {'content-type': 'text/plain'},
                        'body': f"Internal Worker Error:\n{err_msg}"
                    }
                })

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python -m omnicorn.worker <module:app>")
        sys.exit(1)

    worker = OmniWorker(sys.argv[1])
    worker.run()

import sys
import os
import importlib
import traceback
import asyncio
import signal
import inspect

from .protocol import AsyncProtocol
from .wsgi import WSGIAdapter
from .asgi import ASGIAdapter
from . import cache

class OmniWorker:
    def __init__(self, app_path, mode):
        self.app = self.load_app(app_path)
        self.sock_path = os.environ.get("OMNICORN_SOCK")

        if not self.sock_path:
            sys.stderr.write("🔥 OMNICORN_SOCK env var missing.\n")
            sys.exit(1)

        # Autodetect ASGI vs WSGI
        if mode == 'auto':
            if inspect.iscoroutinefunction(self.app) or inspect.iscoroutinefunction(getattr(self.app, '__call__', None)):
                self.app_type = b'asgi'
            else:
                self.app_type = b'wsgi'
        else:
            self.app_type = mode.encode('utf-8')

        self.write_lock = asyncio.Lock()

    def load_app(self, path):
        try:
            mod_name, var_name = path.split(":")
            mod = importlib.import_module(mod_name)
            return getattr(mod, var_name)
        except Exception:
            sys.stderr.write(f"🔥 Failed to load app: {path}\n")
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)

    async def _handle_request(self, msg, writer):
        """Isolated Task for multiplexed processing."""
        req_id = msg.get(b'id')
        msg_type = msg.get(b'type')
        payload = msg.get(b'payload', {})

        try:
            if self.app_type == b'asgi':
                # Direct async execution
                response_data = await ASGIAdapter.run_phase(self.app, msg_type, payload)
            else:
                if msg_type == b'http':
                    # Offload WSGI to thread-pool so it doesn't block multiplexing!
                    response_data = await asyncio.to_thread(WSGIAdapter.run, self.app, payload)
                else:
                    response_data = {b'status': 500, b'body': b"WSGI app cannot handle WebSockets"}

            await AsyncProtocol.write(writer, self.write_lock, {b'id': req_id, b'data': response_data})

        except Exception:
            err = traceback.format_exc()
            sys.stderr.write(f"Worker Request Error: {err}\n")
            await AsyncProtocol.write(writer, self.write_lock, {
                b'id': req_id,
                b'data': {b'status': 500, b'body': b"Internal Worker Error"}
            })

    async def async_run(self):
            try:
                reader, writer = await asyncio.open_unix_connection(self.sock_path)
            except Exception as e:
                sys.stderr.write(f"🔥 Could not connect to UDS {self.sock_path}: {e}\n")
                sys.exit(1)

            # Wire up the global cache IPC
            cache._ipc_writer = writer
            cache._ipc_lock = self.write_lock

            await AsyncProtocol.write(writer, self.write_lock, {
                b'status': b'ready',
                b'pid': os.getpid(),
                b'type': self.app_type
            })

            while True:
                msg = await AsyncProtocol.read(reader)
                if msg is None:
                    break

                msg_type = msg.get(b'type')

                # 🔥 Check if this is a fast-path RPC reply from Erlang
                if msg_type == b'ets_reply':
                    req_id = msg.get(b'id')
                    fut = cache._pending_calls.pop(req_id, None)
                    if fut and not fut.done():
                        fut.set_result(msg.get(b'data'))
                else:
                    # Standard HTTP/WS inbound traffic
                    asyncio.create_task(self._handle_request(msg, writer))

            writer.close()
            await writer.wait_closed()

    def run(self):
        asyncio.run(self.async_run())

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
    mode = os.environ.get("OMNICORN_MODE", "auto")
    OmniWorker(sys.argv[1], mode).run()

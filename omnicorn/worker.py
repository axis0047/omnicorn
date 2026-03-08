import sys
import os
import importlib
import traceback
import asyncio
import signal
import inspect
import erlpack

from .protocol import AsyncProtocol
from .wsgi import WSGIAdapter
from .asgi import ASGIAdapter
from . import cache

# Import the global registry where decorators store the tasks
try:
    from .tasks import TASK_REGISTRY
except ImportError:
    TASK_REGISTRY = {}

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

        # Lock to prevent concurrent multiplexed tasks from interleaving ETF bytes
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
        """Processes incoming HTTP and WebSocket multiplexed traffic."""
        req_id = msg.get(b'id')
        msg_type = msg.get(b'type')
        payload = msg.get(b'payload', {})

        try:
            if self.app_type == b'asgi':
                # Direct async execution for ASGI
                response_data = await ASGIAdapter.run_phase(self.app, msg_type, payload)
            else:
                if msg_type == b'http':
                    # Offload WSGI to a thread-pool so it doesn't block the multiplexing loop!
                    response_data = await asyncio.to_thread(WSGIAdapter.run, self.app, payload)
                else:
                    response_data = {b'status': 500, b'body': b"WSGI app cannot handle WebSockets"}

            # Safely write the response back to Erlang
            await AsyncProtocol.write(writer, self.write_lock, {b'id': req_id, b'data': response_data})

        except Exception:
            err = traceback.format_exc()
            sys.stderr.write(f"Worker Request Error: {err}\n")
            await AsyncProtocol.write(writer, self.write_lock, {
                b'id': req_id,
                b'data': {b'status': 500, b'body': b"Internal Worker Error"}
            })

    async def _execute_background_task(self, msg, writer):
        """Processes background ETL/Worker tasks deferred by Erlang."""
        payload = msg.get(b'payload', {})
        task_name = payload.get(b'name', b'').decode('utf-8')
        task_id = payload.get(b'task_id')

        # Safely unpack the ETF binary arguments
        try:
            args = erlpack.unpack(payload.get(b'args')) if b'args' in payload else ()
            kwargs = erlpack.unpack(payload.get(b'kwargs')) if b'kwargs' in payload else {}
        except Exception as e:
            sys.stderr.write(f"Task Unpack Error: {e}\n")
            args, kwargs = (), {}

        target_task = TASK_REGISTRY.get(task_name)

        if target_task:
            try:
                # Execute dynamically based on whether the developer wrote an async or sync function
                if asyncio.iscoroutinefunction(target_task.func):
                    await target_task.func(*args, **kwargs)
                else:
                    await asyncio.to_thread(target_task.func, *args, **kwargs)

                # Acknowledge success to Erlang (so Erlang drops it from Mnesia/ETS)
                await AsyncProtocol.write(writer, self.write_lock, {
                    b'type': b'task_ack',
                    b'task_id': task_id
                })
            except Exception as e:
                err_msg = str(e).encode('utf-8')
                sys.stderr.write(f"Background Task '{task_name}' Failed: {e}\n")

                # Report failure so Erlang can decrement the retry counter and re-queue it
                await AsyncProtocol.write(writer, self.write_lock, {
                    b'type': b'task_fail',
                    b'task_id': task_id,
                    b'error': err_msg
                })
        else:
            sys.stderr.write(f"Received unknown task: {task_name}\n")
            await AsyncProtocol.write(writer, self.write_lock, {
                b'type': b'task_fail',
                b'task_id': task_id,
                b'error': b'Task not registered in Python worker'
            })

    async def async_run(self):
        """The main multiplexed event loop bridging Python to Erlang."""
        try:
            reader, writer = await asyncio.open_unix_connection(self.sock_path)
        except Exception as e:
            sys.stderr.write(f"🔥 Could not connect to UDS {self.sock_path}: {e}\n")
            sys.exit(1)

        # Wire up the global Cache IPC channels so user code can use `omnicorn.get()`
        cache._ipc_writer = writer
        cache._ipc_lock = self.write_lock

        # Send Worker Handshake
        await AsyncProtocol.write(writer, self.write_lock, {
            b'status': b'ready',
            b'pid': os.getpid(),
            b'type': self.app_type
        })

        # Infinite Multiplexing Loop
        while True:
            msg = await AsyncProtocol.read(reader)

            # Connection closed by Erlang Master (e.g., scale down or restart)
            if msg is None:
                break

            msg_type = msg.get(b'type')

            # 1. FAST PATH: Erlang answering a cache query (ets_get, ets_set)
            if msg_type == b'ets_reply':
                req_id = msg.get(b'id')
                fut = cache._pending_calls.pop(req_id, None)
                if fut and not fut.done():
                    fut.set_result(msg.get(b'data'))

            # 2. BACKGROUND TASK: Erlang pushing an ETL / Offline job
            elif msg_type == b'task_execute':
                # Fire & Forget! Does not block HTTP traffic.
                asyncio.create_task(self._execute_background_task(msg, writer))

            # 3. STANDARD TRAFFIC: HTTP Requests & WebSockets
            else:
                # Fire & Forget! Does not block other incoming requests.
                asyncio.create_task(self._handle_request(msg, writer))

        writer.close()
        await writer.wait_closed()

    def run(self):
        """Entrypoint called by the OS process."""
        asyncio.run(self.async_run())

if __name__ == "__main__":
    # Ensure graceful exit if Erlang sends SIGTERM
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
    mode = os.environ.get("OMNICORN_MODE", "auto")
    OmniWorker(sys.argv[1], mode).run()

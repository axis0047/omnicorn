import asyncio
import importlib
import inspect
import os
import signal
import sys
import traceback

from . import cache
from .orchestrator.activities import execute_activity
from .orchestrator.sagas import execute_workflow_step
from .transport import PyUDSTransport
from .web.asgi import ASGIAdapter
from .web.wsgi import WSGIAdapter


class OmniWorker:
    def __init__(self, app_path, mode):
        self.app = self.load_app(app_path)
        sock_path = os.environ.get("OMNICORN_SOCK")
        self.transport = PyUDSTransport(sock_path)

        if mode == "auto":
            self.app_type = (
                b"asgi"
                if inspect.iscoroutinefunction(self.app)
                or inspect.iscoroutinefunction(getattr(self.app, "__call__", None))
                else b"wsgi"
            )
        else:
            self.app_type = mode.encode("utf-8")

    def load_app(self, path):
        try:
            mod_name, var_name = path.split(":")
            return getattr(importlib.import_module(mod_name), var_name)
        except Exception:
            sys.stderr.write(f"🔥 Failed to load app: {path}\n")
            traceback.print_exc(file=sys.stderr)
            sys.exit(1)

    async def async_run(self):
        await self.transport.connect()
        cache._ipc_transport = self.transport

        await self.transport.send(
            {b"status": b"ready", b"pid": os.getpid(), b"type": self.app_type}
        )

        while True:
            msg = await self.transport.recv()
            if msg is None:
                break

            msg_type = msg.get(b"type")

            # --- CACHE ---
            if msg_type == b"ets_reply":
                req_id = msg.get(b"id")
                fut = cache._pending_calls.pop(req_id, None)
                if fut and not fut.done():
                    fut.set_result(msg.get(b"data"))

            # --- ORCHESTRATOR / WORKFLOWS ---
            elif msg_type == b"workflow_execute":
                asyncio.create_task(execute_workflow_step(msg, self.transport))

            # --- BACKGROUND ACTIVITIES ---
            elif msg_type == b"activity_execute":
                asyncio.create_task(execute_activity(msg, self.transport))

            # --- WEB TRAFFIC ---
            else:
                asyncio.create_task(self._handle_web_request(msg))

        await self.transport.close()

    async def _handle_web_request(self, msg):
        req_id = msg.get(b"id")
        msg_type = msg.get(b"type")
        payload = msg.get(b"payload", {})
        try:
            if self.app_type == b"asgi":
                resp = await ASGIAdapter.run_phase(
                    self.app, msg_type, payload, self.transport
                )
            else:
                resp = (
                    await asyncio.to_thread(WSGIAdapter.run, self.app, payload)
                    if msg_type == b"http"
                    else {b"status": 500, b"body": b"WSGI non-HTTP error"}
                )

            # 🔥 Only send a reply if it's an HTTP/Handshake cycle
            if resp is not None:
                await self.transport.send({b"id": req_id, b"data": resp})
        except Exception as e:
            sys.stderr.write(f"Web Error: {traceback.format_exc()}\n")
            if req_id:
                await self.transport.send(
                    {
                        b"id": req_id,
                        b"data": {b"status": 500, b"body": b"Internal Error"},
                    }
                )

    def run(self):
        asyncio.run(self.async_run())


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))
    OmniWorker(sys.argv[1], os.environ.get("OMNICORN_MODE", "auto")).run()

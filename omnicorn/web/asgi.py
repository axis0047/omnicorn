import asyncio
import sys
import traceback

WS_CONNECTIONS = {}


class ASGIAdapter:
    @staticmethod
    async def run_phase(app, msg_type, etf_payload, transport):
        if msg_type == b"http":
            return await ASGIAdapter._handle_http_request(app, etf_payload)
        elif msg_type == b"websocket_handshake":
            return await ASGIAdapter._handle_websocket_handshake(app, etf_payload)
        elif msg_type == b"websocket_message":
            return await ASGIAdapter._handle_websocket_message(app, etf_payload)
        elif msg_type == b"websocket_disconnect":
            return await ASGIAdapter._handle_websocket_disconnect(app, etf_payload)

    @staticmethod
    def _parse_headers(etf_payload):
        return [
            (
                k if isinstance(k, bytes) else str(k).encode("utf-8").lower(),
                v if isinstance(v, bytes) else str(v).encode("utf-8"),
            )
            for k, v in (
                etf_payload.get(b"headers", {}).items()
                if isinstance(etf_payload.get(b"headers", {}), dict)
                else etf_payload.get(b"headers", [])
            )
        ]

    @staticmethod
    async def _handle_http_request(app, p):
        # FIX: Added required ASGI keys: raw_path, query_string, server, client
        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": p.get(b"method", b"GET").decode("utf-8"),
            "scheme": p.get(b"scheme", b"http").decode("utf-8"),
            "path": p.get(b"path", b"/").decode("utf-8"),
            "raw_path": p.get(b"path", b"/"),
            "query_string": p.get(b"query", b""),
            "headers": ASGIAdapter._parse_headers(p),
            "server": ("127.0.0.1", int(p.get(b"port", 80))),
            "client": ("127.0.0.1", 0),
        }
        res = {"status": 500, "headers": {}, "body": b""}
        q = asyncio.Queue()
        q.put_nowait({"type": "http.request", "body": p.get(b"body", b"")})

        async def send(msg):
            if msg["type"] == "http.response.start":
                res["status"] = msg["status"]
                for k, v in msg.get("headers", []):
                    res["headers"][k] = v
            elif msg["type"] == "http.response.body":
                res["body"] += msg.get("body", b"")

        try:
            await app(scope, q.get, send)
        except Exception:
            sys.stderr.write(f"ASGI HTTP Error: {traceback.format_exc()}\n")

        return {
            b"status": res["status"],
            b"headers": res["headers"],
            b"body": res["body"],
        }

    @staticmethod
    async def _handle_websocket_handshake(app, p):
        req_id = p.get(b"id")
        # FIX: Added required ASGI WS keys
        scope = {
            "type": "websocket",
            "asgi": {"version": "3.0"},
            "scheme": p.get(b"scheme", b"ws").decode("utf-8"),
            "path": p.get(b"path", b"/").decode("utf-8"),
            "raw_path": p.get(b"path", b"/"),
            "query_string": p.get(b"query", b""),
            "headers": ASGIAdapter._parse_headers(p),
            "server": ("127.0.0.1", int(p.get(b"port", 80))),
            "client": ("127.0.0.1", 0),
            "subprotocols": [],
            "state": {},
        }
        rq, sq = asyncio.Queue(), asyncio.Queue()
        rq.put_nowait({"type": "websocket.connect"})
        WS_CONNECTIONS[req_id] = {
            "rq": rq,
            "sq": sq,
            "task": asyncio.create_task(app(scope, rq.get, sq.put)),
        }
        try:
            msg = await asyncio.wait_for(sq.get(), 3.0)
            if msg["type"] == "websocket.accept":
                return {b"websocket_handshake": b"accept"}
            return {b"websocket_handshake": b"close"}
        except Exception:
            sys.stderr.write(f"ASGI WS Error: {traceback.format_exc()}\n")
            return {b"websocket_handshake": b"error"}

    @staticmethod
    async def _handle_websocket_message(app, p):
        req_id = p.get(b"id")
        c = WS_CONNECTIONS.get(req_id)
        if not c:
            return {b"websocket_message_response": []}
        msg_type, content = p.get(b"message_type"), p.get(b"content")
        c["rq"].put_nowait(
            {"type": "websocket.receive", "text": content.decode("utf-8")}
            if msg_type == b"text"
            else {"type": "websocket.receive", "bytes": content}
        )
        await asyncio.sleep(0.005)  # Yield to ASGI Task
        out = []
        while not c["sq"].empty():
            msg = c["sq"].get_nowait()
            if msg["type"] == "websocket.send":
                out.append(
                    {b"type": b"send_text", b"content": msg["text"].encode("utf-8")}
                    if "text" in msg
                    else {b"type": b"send_binary", b"content": msg["bytes"]}
                )
            elif msg["type"] == "websocket.close":
                out.append({b"type": b"close"})
        return {b"websocket_message_response": out}

    @staticmethod
    async def _handle_websocket_disconnect(app, p):
        req_id = p.get(b"id")
        if req_id in WS_CONNECTIONS:
            WS_CONNECTIONS[req_id]["rq"].put_nowait({"type": "websocket.disconnect"})
            del WS_CONNECTIONS[req_id]
        return {b"websocket_disconnect_response": b"ok"}

import asyncio

_ipc_transport = None
_pending_calls = {}
_req_counter = 0


async def get(key: str):
    res = await _rpc_call(b"ets_get", {b"key": key.encode("utf-8")})
    return None if res == b"nil" else res


async def set(key: str, value, ttl_ms: int = 0):
    if isinstance(value, str):
        value = value.encode("utf-8")
    return await _rpc_call(
        b"ets_set", {b"key": key.encode("utf-8"), b"value": value, b"ttl": ttl_ms}
    )


async def delete(key: str):
    return await _rpc_call(b"ets_delete", {b"key": key.encode("utf-8")})


async def incr(key: str, amount: int = 1):
    return await _rpc_call(
        b"ets_incr", {b"key": key.encode("utf-8"), b"amount": amount}
    )


async def _rpc_call(call_type: bytes, payload: dict):
    global _req_counter, _ipc_transport
    _req_counter += 1
    req_id = f"py_{_req_counter}".encode("utf-8")

    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    _pending_calls[req_id] = fut

    await _ipc_transport.send({b"id": req_id, b"type": call_type, b"payload": payload})
    return await fut

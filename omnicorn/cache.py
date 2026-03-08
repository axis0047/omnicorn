import asyncio

_ipc_writer = None
_ipc_lock = None
_pending_calls = {}
_req_counter = 0

async def get(key: str):
    res = await _rpc_call(b'ets_get', {b'key': key.encode('utf-8')})
    if res == b'nil': return None
    return res

async def set(key: str, value, ttl_ms: int = 0):
    """Set a value. ttl_ms is Time-To-Live in milliseconds."""
    if isinstance(value, str): value = value.encode('utf-8')
    return await _rpc_call(b'ets_set', {
        b'key': key.encode('utf-8'),
        b'value': value,
        b'ttl': ttl_ms
    })

async def delete(key: str):
    """Instantly evict a key globally."""
    return await _rpc_call(b'ets_delete', {b'key': key.encode('utf-8')})

async def incr(key: str, amount: int = 1):
    """
    Atomic lock-free counter. Perfect for rate-limiting.
    Returns the new integer value.
    """
    return await _rpc_call(b'ets_incr', {b'key': key.encode('utf-8'), b'amount': amount})

async def _rpc_call(call_type: bytes, payload: dict):
    global _req_counter, _ipc_writer, _ipc_lock
    if not _ipc_writer:
        raise RuntimeError("Omnicorn IPC not initialized.")

    _req_counter += 1
    # Use string prefix to guarantee Python-originated IDs never collide with Erlang HTTP Req IDs
    req_id = f"py_{_req_counter}".encode('utf-8')

    loop = asyncio.get_running_loop()
    fut = loop.create_future()
    _pending_calls[req_id] = fut

    from .protocol import AsyncProtocol
    await AsyncProtocol.write(_ipc_writer, _ipc_lock, {
        b'id': req_id,
        b'type': call_type,
        b'payload': payload
    })

    return await fut

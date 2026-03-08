import asyncio

_ipc_writer = None
_ipc_lock = None
_pending_calls = {}
_req_counter = 0

async def get(key: str):
    """Fetch a value from Erlang Term Storage (ETS) in microseconds."""
    res = await _rpc_call(b'ets_get', {b'key': key.encode('utf-8')})
    if res == b'nil': return None
    return res

async def set(key: str, value):
    """Set a value in Erlang Term Storage (ETS) available to ALL workers instantly."""
    if isinstance(value, str): value = value.encode('utf-8')
    return await _rpc_call(b'ets_set', {b'key': key.encode('utf-8'), b'value': value})

async def _rpc_call(call_type: bytes, payload: dict):
    global _req_counter, _ipc_writer, _ipc_lock
    if not _ipc_writer:
        raise RuntimeError("Omnicorn IPC not initialized.")

    _req_counter += 1
    req_id = _req_counter
    loop = asyncio.get_running_loop()

    # Create a Future that will suspend this specific task until Erlang replies
    fut = loop.create_future()
    _pending_calls[req_id] = fut

    from .protocol import AsyncProtocol
    await AsyncProtocol.write(_ipc_writer, _ipc_lock, {
        b'id': req_id,
        b'type': call_type,
        b'payload': payload
    })

    return await fut

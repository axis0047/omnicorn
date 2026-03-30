import asyncio
import itertools
from typing import Any, Optional

_ipc_transport: Optional[Any] = None
_pending_calls: dict = {}
_req_counter = itertools.count()
_lock = asyncio.Lock()


async def get(key: str):
    """Get value from distributed cache."""
    res = await _rpc_call(b"ets_get", {b"key": key.encode("utf-8")})
    return None if res == b"nil" else res


async def set(key: str, value, ttl_ms: int = 0):
    """Set value in distributed cache with optional TTL."""
    return await _rpc_call(
        b"ets_set", 
        {b"key": key.encode("utf-8"), b"value": value, b"ttl": ttl_ms}
    )


async def delete(key: str):
    """Delete value from cache."""
    res = await _rpc_call(b"ets_delete", {b"key": key.encode("utf-8")})
    return res == b"ok"


async def incr(key: str, amount: int = 1):
    """Atomically increment counter."""
    return await _rpc_call(
        b"ets_incr", 
        {b"key": key.encode("utf-8"), b"amount": amount}
    )


async def _rpc_call(call_type: bytes, payload: dict) -> Any:
    """Internal RPC call with proper locking and cleanup."""
    global _pending_calls
    
    if _ipc_transport is None:
        raise RuntimeError("Cache not initialized (no transport)")
    
    async with _lock:
        req_id = f"py_{next(_req_counter)}".encode("utf-8")
        
        # Cleanup completed futures to prevent memory leak
        _pending_calls = {
            k: v for k, v in _pending_calls.items() 
            if not v.done()
        }
        
        loop = asyncio.get_running_loop()
        fut = loop.create_future()
        _pending_calls[req_id] = fut
    
    try:
        await _ipc_transport.send({
            b"id": req_id, 
            b"type": call_type, 
            b"payload": payload
        })
        return await fut
    except Exception as e:
        # Cleanup on error
        async with _lock:
            _pending_calls.pop(req_id, None)
        raise

"""
Omnicorn Distributed Cache API

A high-performance distributed cache backed by Erlang ETS tables.

Usage:
    from omnicorn import cache
    
    # Simple get/set
    await cache.set("user:123", {"name": "John"})
    user = await cache.get("user:123")
    
    # With TTL (1 hour)
    await cache.set("session:abc", data, ttl_ms=3600000)
    
    # Atomic increment
    count = await cache.incr("page:views")
    
    # Delete
    await cache.delete("key")
"""

import asyncio
import itertools
from typing import Any, Dict, Optional, Union

# Type aliases
CacheKey = str
CacheValue = Any
TTLMilliseconds = int


class CacheError(Exception):
    """Base exception for cache operations."""
    pass


class CacheConnectionError(CacheError):
    """Raised when cache connection is lost."""
    pass


class CacheNotInitializedError(CacheError):
    """Raised when cache is accessed before initialization."""
    pass


# Module state
_ipc_transport: Optional[Any] = None
_pending_calls: Dict[bytes, asyncio.Future] = {}
_req_counter = itertools.count()
_lock = asyncio.Lock()


async def get(key: CacheKey) -> Optional[CacheValue]:
    """
    Get value from distributed cache.
    
    Args:
        key: Cache key (string)
    
    Returns:
        Value if exists, None otherwise
    
    Raises:
        CacheConnectionError: If cache connection is lost
    """
    try:
        res = await _rpc_call(b"ets_get", {b"key": key.encode("utf-8")})
        return None if res == b"nil" else res
    except RuntimeError as e:
        raise CacheConnectionError(f"Failed to get key '{key}': {e}")


async def set(
    key: CacheKey,
    value: CacheValue,
    ttl_ms: TTLMilliseconds = 0
) -> bool:
    """
    Set value in distributed cache.
    
    Args:
        key: Cache key (string)
        value: Any Python object (automatically serialized)
        ttl_ms: Time-to-live in milliseconds (0 = no expiry)
    
    Returns:
        True on success
    
    Raises:
        CacheConnectionError: If cache connection is lost
    """
    try:
        await _rpc_call(
            b"ets_set",
            {
                b"key": key.encode("utf-8"),
                b"value": value,  # Erlang handles serialization
                b"ttl": ttl_ms
            }
        )
        return True
    except RuntimeError as e:
        raise CacheConnectionError(f"Failed to set key '{key}': {e}")


async def delete(key: CacheKey) -> bool:
    """
    Delete value from cache.
    
    Args:
        key: Cache key (string)
    
    Returns:
        True if deleted, False if key didn't exist
    
    Raises:
        CacheConnectionError: If cache connection is lost
    """
    try:
        res = await _rpc_call(b"ets_delete", {b"key": key.encode("utf-8")})
        return res == b"ok"
    except RuntimeError as e:
        raise CacheConnectionError(f"Failed to delete key '{key}': {e}")


async def incr(key: CacheKey, amount: int = 1) -> int:
    """
    Atomically increment counter.
    
    Args:
        key: Cache key (string)
        amount: Amount to increment by (default 1)
    
    Returns:
        New counter value
    
    Raises:
        CacheConnectionError: If cache connection is lost
        CacheError: If key doesn't exist or is not a counter
    """
    try:
        res = await _rpc_call(
            b"ets_incr",
            {b"key": key.encode("utf-8"), b"amount": amount}
        )
        if res is None:
            raise CacheError(f"Counter '{key}' not found or invalid")
        return res
    except RuntimeError as e:
        raise CacheConnectionError(f"Failed to increment key '{key}': {e}")


async def stats() -> Dict[str, Any]:
    """
    Get cache statistics.
    
    Returns:
        Dictionary with cache stats:
        - size: Number of entries in cache
        - pending: Number of pending RPC calls
    
    Raises:
        CacheConnectionError: If cache connection is lost
    """
    try:
        res = await _rpc_call(b"ets_stats", {})
        return res if isinstance(res, dict) else {}
    except RuntimeError as e:
        raise CacheConnectionError(f"Failed to get stats: {e}")


async def _rpc_call(call_type: bytes, payload: dict) -> Any:
    """
    Internal RPC call with proper locking and cleanup.
    
    Args:
        call_type: Type of RPC call
        payload: Call payload
    
    Returns:
        RPC response
    
    Raises:
        CacheNotInitializedError: If cache transport not initialized
        RuntimeError: If send fails
    """
    global _pending_calls
    
    if _ipc_transport is None:
        raise CacheNotInitializedError(
            "Cache not initialized - transport is None. "
            "Ensure Omnicorn worker is running."
        )
    
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
        raise RuntimeError(f"RPC call failed: {e}")


def _initialize(transport: Any) -> None:
    """
    Initialize cache with IPC transport.
    Called internally by Omnicorn worker.
    
    Args:
        transport: IPC transport instance
    """
    global _ipc_transport
    _ipc_transport = transport


def _cleanup() -> None:
    """
    Cleanup cache state.
    Called internally on worker shutdown.
    """
    global _ipc_transport, _pending_calls
    _ipc_transport = None
    _pending_calls = {}

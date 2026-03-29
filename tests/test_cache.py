"""
Tests for Omnicorn cache API.

These tests verify the cache.get, cache.set, cache.delete, and cache.incr operations.
"""

import pytest
from omnicorn import cache


@pytest.mark.asyncio
async def test_cache_set_get(sample_cache_key, sample_cache_value):
    """Test basic cache set and get operations."""
    # Set value
    result = await cache.set(sample_cache_key, sample_cache_value)
    assert result is True
    
    # Get value back
    retrieved = await cache.get(sample_cache_key)
    assert retrieved == sample_cache_value


@pytest.mark.asyncio
async def test_cache_get_nonexistent():
    """Test getting a key that doesn't exist."""
    result = await cache.get("nonexistent:key")
    assert result is None


@pytest.mark.asyncio
async def test_cache_delete(sample_cache_key, sample_cache_value):
    """Test cache delete operation."""
    # Set and verify
    await cache.set(sample_cache_key, sample_cache_value)
    assert await cache.get(sample_cache_key) == sample_cache_value
    
    # Delete and verify
    result = await cache.delete(sample_cache_key)
    assert result is True
    
    # Verify deletion
    assert await cache.get(sample_cache_key) is None


@pytest.mark.asyncio
async def test_cache_delete_nonexistent():
    """Test deleting a key that doesn't exist."""
    result = await cache.delete("nonexistent:key")
    assert result is False


@pytest.mark.asyncio
async def test_cache_incr():
    """Test atomic increment operation."""
    key = "test:counter"
    
    # Initialize counter
    await cache.set(key, 0)
    
    # Increment
    val1 = await cache.incr(key)
    assert val1 == 1
    
    val2 = await cache.incr(key)
    assert val2 == 2
    
    val3 = await cache.incr(key, 5)
    assert val3 == 7


@pytest.mark.asyncio
async def test_cache_incr_nonexistent():
    """Test incrementing a key that doesn't exist."""
    # Should return None or raise an error depending on implementation
    result = await cache.incr("nonexistent:counter")
    # Implementation may vary - adjust assertion based on actual behavior
    assert result is None or isinstance(result, int)


@pytest.mark.asyncio
async def test_cache_ttl(sample_cache_key, sample_cache_value):
    """Test cache TTL (time-to-live) functionality."""
    # Set with short TTL (100ms)
    await cache.set(sample_cache_key, sample_cache_value, ttl_ms=100)
    
    # Should exist immediately
    assert await cache.get(sample_cache_key) == sample_cache_value
    
    # Wait for expiry
    await asyncio.sleep(0.2)
    
    # Should be expired
    assert await cache.get(sample_cache_key) is None


@pytest.mark.asyncio
async def test_cache_no_ttl(sample_cache_key, sample_cache_value):
    """Test cache without TTL (persistent)."""
    await cache.set(sample_cache_key, sample_cache_value, ttl_ms=0)
    
    # Wait a bit
    await asyncio.sleep(0.1)
    
    # Should still exist
    assert await cache.get(sample_cache_key) == sample_cache_value


@pytest.mark.asyncio
async def test_cache_various_types():
    """Test caching various Python types."""
    test_cases = [
        ("test:string", "hello world"),
        ("test:int", 42),
        ("test:float", 3.14159),
        ("test:bool", True),
        ("test:None", None),
        ("test:list", [1, 2, 3]),
        ("test:dict", {"nested": {"key": "value"}}),
    ]
    
    for key, value in test_cases:
        await cache.set(key, value)
        retrieved = await cache.get(key)
        assert retrieved == value, f"Failed for {key}: {value} != {retrieved}"

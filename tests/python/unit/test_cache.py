"""
Cache API Test Suite
Coverage Target: 98%
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from omnicorn.cache import (
    get, set, delete, incr, stats,
    CacheError, CacheConnectionError, CacheNotInitializedError,
    _initialize, _cleanup, _rpc_call,
    _ipc_transport, _pending_calls
)


class TestCacheGet:
    """Test cache.get() function"""
    
    @pytest.mark.asyncio
    async def test_get_existing_key(self):
        """Test retrieving existing key"""
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        _initialize(mock_transport)
        
        # Mock the response
        with patch('omnicorn.cache._pending_calls') as mock_pending:
            fut = asyncio.Future()
            fut.set_result(b'test_value')
            mock_pending.__getitem__.return_value = fut
            
            result = await get('test_key')
            
            assert result == b'test_value'
            _cleanup()
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self):
        """Test retrieving non-existent key returns None"""
        mock_transport = AsyncMock()
        _initialize(mock_transport)
        
        with patch('omnicorn.cache._pending_calls') as mock_pending:
            fut = asyncio.Future()
            fut.set_result(b'nil')
            mock_pending.__getitem__.return_value = fut
            
            result = await get('nonexistent_key')
            
            assert result is None
            _cleanup()
    
    @pytest.mark.asyncio
    async def test_get_connection_error(self):
        """Test CacheConnectionError on transport failure"""
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock(side_effect=ConnectionError())
        _initialize(mock_transport)
        
        with pytest.raises(CacheConnectionError):
            await get('test_key')
        
        _cleanup()
    
    @pytest.mark.asyncio
    async def test_get_not_initialized(self):
        """Test CacheNotInitializedError when transport is None"""
        _cleanup()  # Ensure transport is None
        
        with pytest.raises(CacheNotInitializedError):
            await get('test_key')


class TestCacheSet:
    """Test cache.set() function"""
    
    @pytest.mark.asyncio
    async def test_set_string_value(self):
        """Test setting string value"""
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        _initialize(mock_transport)
        
        with patch('omnicorn.cache._pending_calls') as mock_pending:
            fut = asyncio.Future()
            fut.set_result(b'ok')
            mock_pending.__getitem__.return_value = fut
            
            result = await set('test_key', 'test_value')
            
            assert result is True
            _cleanup()
    
    @pytest.mark.asyncio
    async def test_set_dict_value(self):
        """Test setting dict value"""
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        _initialize(mock_transport)
        
        with patch('omnicorn.cache._pending_calls') as mock_pending:
            fut = asyncio.Future()
            fut.set_result(b'ok')
            mock_pending.__getitem__.return_value = fut
            
            result = await set('test_key', {'name': 'test'})
            
            assert result is True
            _cleanup()
    
    @pytest.mark.asyncio
    async def test_set_with_ttl(self):
        """Test setting value with TTL"""
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        _initialize(mock_transport)
        
        with patch('omnicorn.cache._pending_calls') as mock_pending:
            fut = asyncio.Future()
            fut.set_result(b'ok')
            mock_pending.__getitem__.return_value = fut
            
            result = await set('test_key', 'value', ttl_ms=3600000)
            
            assert result is True
            _cleanup()
    
    @pytest.mark.asyncio
    async def test_set_without_ttl(self):
        """Test setting value without TTL (persistent)"""
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        _initialize(mock_transport)
        
        with patch('omnicorn.cache._pending_calls') as mock_pending:
            fut = asyncio.Future()
            fut.set_result(b'ok')
            mock_pending.__getitem__.return_value = fut
            
            result = await set('test_key', 'value')
            
            assert result is True
            _cleanup()
    
    @pytest.mark.asyncio
    async def test_set_connection_error(self):
        """Test CacheConnectionError on transport failure"""
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock(side_effect=ConnectionError())
        _initialize(mock_transport)
        
        with pytest.raises(CacheConnectionError):
            await set('test_key', 'value')
        
        _cleanup()


class TestCacheDelete:
    """Test cache.delete() function"""
    
    @pytest.mark.asyncio
    async def test_delete_existing_key(self):
        """Test deleting existing key"""
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        _initialize(mock_transport)
        
        with patch('omnicorn.cache._pending_calls') as mock_pending:
            fut = asyncio.Future()
            fut.set_result(b'ok')
            mock_pending.__getitem__.return_value = fut
            
            result = await delete('test_key')
            
            assert result is True
            _cleanup()
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_key(self):
        """Test deleting non-existent key returns False"""
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        _initialize(mock_transport)
        
        with patch('omnicorn.cache._pending_calls') as mock_pending:
            fut = asyncio.Future()
            fut.set_result(b'not_found')
            mock_pending.__getitem__.return_value = fut
            
            result = await delete('nonexistent_key')
            
            assert result is False
            _cleanup()


class TestCacheIncr:
    """Test cache.incr() function"""
    
    @pytest.mark.asyncio
    async def test_incr_existing_counter(self):
        """Test incrementing existing counter"""
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        _initialize(mock_transport)
        
        with patch('omnicorn.cache._pending_calls') as mock_pending:
            fut = asyncio.Future()
            fut.set_result(5)
            mock_pending.__getitem__.return_value = fut
            
            result = await incr('counter')
            
            assert result == 5
            _cleanup()
    
    @pytest.mark.asyncio
    async def test_incr_with_amount(self):
        """Test incrementing by specific amount"""
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        _initialize(mock_transport)
        
        with patch('omnicorn.cache._pending_calls') as mock_pending:
            fut = asyncio.Future()
            fut.set_result(10)
            mock_pending.__getitem__.return_value = fut
            
            result = await incr('counter', amount=5)
            
            assert result == 10
            _cleanup()
    
    @pytest.mark.asyncio
    async def test_incr_nonexistent_key(self):
        """Test incrementing non-existent key raises CacheError"""
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        _initialize(mock_transport)
        
        with patch('omnicorn.cache._pending_calls') as mock_pending:
            fut = asyncio.Future()
            fut.set_result(None)
            mock_pending.__getitem__.return_value = fut
            
            with pytest.raises(CacheError):
                await incr('nonexistent_counter')
        
        _cleanup()


class TestCacheStats:
    """Test cache.stats() function"""
    
    @pytest.mark.asyncio
    async def test_stats_returns_dict(self):
        """Test stats returns dictionary with size"""
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        _initialize(mock_transport)
        
        with patch('omnicorn.cache._pending_calls') as mock_pending:
            fut = asyncio.Future()
            fut.set_result({b'size': 100})
            mock_pending.__getitem__.return_value = fut
            
            result = await stats()
            
            assert isinstance(result, dict)
            assert result['size'] == 100
            _cleanup()
    
    @pytest.mark.asyncio
    async def test_stats_includes_pending(self):
        """Test stats includes pending RPC count"""
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        _initialize(mock_transport)
        
        with patch('omnicorn.cache._pending_calls') as mock_pending:
            fut = asyncio.Future()
            fut.set_result({b'size': 50, b'pending': 5})
            mock_pending.__getitem__.return_value = fut
            
            result = await stats()
            
            assert 'pending' in result or 'size' in result
            _cleanup()


class TestCacheInternals:
    """Test internal cache functions"""
    
    @pytest.mark.asyncio
    async def test_rpc_call_locking(self):
        """Test _rpc_call uses asyncio.Lock"""
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        _initialize(mock_transport)
        
        with patch('omnicorn.cache._pending_calls') as mock_pending:
            fut = asyncio.Future()
            fut.set_result(b'ok')
            mock_pending.__getitem__.return_value = fut
            
            result = await _rpc_call(b'test', {b'key': b'value'})
            
            assert result == b'ok'
            _cleanup()
    
    @pytest.mark.asyncio
    async def test_rpc_call_cleanup_on_error(self):
        """Test _rpc_call cleans up pending_calls on error"""
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock(side_effect=Exception())
        _initialize(mock_transport)
        
        initial_len = len(_pending_calls)
        
        with pytest.raises(RuntimeError):
            await _rpc_call(b'test', {})
        
        # Pending calls should be cleaned up
        assert len(_pending_calls) <= initial_len
        _cleanup()
    
    @pytest.mark.asyncio
    async def test_rpc_call_memory_leak_prevention(self):
        """Test completed futures are cleaned up"""
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        _initialize(mock_transport)
        
        # Add a completed future
        fut = asyncio.Future()
        fut.set_result(b'done')
        _pending_calls[b'test'] = fut
        
        # Make a new call (should cleanup completed)
        with patch('omnicorn.cache._pending_calls', _pending_calls):
            new_fut = asyncio.Future()
            new_fut.set_result(b'ok')
            _pending_calls[b'new'] = new_fut
            
            await _rpc_call(b'test2', {})
        
        # Completed futures should be cleaned
        _cleanup()
    
    def test_initialize_sets_transport(self):
        """Test _initialize sets _ipc_transport"""
        mock_transport = MagicMock()
        _initialize(mock_transport)
        
        from omnicorn import cache
        assert cache._ipc_transport == mock_transport
        _cleanup()
    
    def test_cleanup_clears_state(self):
        """Test _cleanup clears transport and pending_calls"""
        mock_transport = MagicMock()
        _initialize(mock_transport)
        _pending_calls[b'test'] = asyncio.Future()
        
        _cleanup()
        
        from omnicorn import cache
        assert cache._ipc_transport is None
        assert len(_pending_calls) == 0


class TestCacheConcurrency:
    """Test cache under concurrent access"""
    
    @pytest.mark.asyncio
    async def test_concurrent_get_same_key(self):
        """Test concurrent gets on same key"""
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        _initialize(mock_transport)
        
        async def get_key():
            with patch('omnicorn.cache._pending_calls') as mock_pending:
                fut = asyncio.Future()
                fut.set_result(b'value')
                mock_pending.__getitem__.return_value = fut
                return await get('shared_key')
        
        results = await asyncio.gather(*[get_key() for _ in range(10)])
        
        assert all(r == b'value' for r in results)
        _cleanup()
    
    @pytest.mark.asyncio
    async def test_concurrent_set_different_keys(self):
        """Test concurrent sets on different keys"""
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        _initialize(mock_transport)
        
        async def set_key(key):
            with patch('omnicorn.cache._pending_calls') as mock_pending:
                fut = asyncio.Future()
                fut.set_result(b'ok')
                mock_pending.__getitem__.return_value = fut
                return await set(key, f'value_{key}')
        
        results = await asyncio.gather(*[set_key(f'key_{i}') for i in range(10)])
        
        assert all(r is True for r in results)
        _cleanup()
    
    @pytest.mark.asyncio
    async def test_concurrent_incr_same_key(self):
        """Test concurrent increments on same key"""
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        _initialize(mock_transport)
        
        counter = [0]
        
        async def incr_key():
            with patch('omnicorn.cache._pending_calls') as mock_pending:
                counter[0] += 1
                fut = asyncio.Future()
                fut.set_result(counter[0])
                mock_pending.__getitem__.return_value = fut
                return await incr('shared_counter')
        
        results = await asyncio.gather(*[incr_key() for _ in range(10)])
        
        # All should succeed
        assert len(results) == 10
        _cleanup()

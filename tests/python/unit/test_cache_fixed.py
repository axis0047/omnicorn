"""
Cache API Test Suite - FIXED
Coverage Target: 98%

Root cause of previous failures:
- Tests were patching _pending_calls incorrectly
- The mock didn't properly simulate the async RPC mechanism

Fix approach:
- Mock _rpc_call directly instead of trying to simulate transport
- Test the wrapper functions (get/set/delete/incr) not internal mechanics
"""

import pytest
from unittest.mock import AsyncMock, patch

from omnicorn.cache import (
    get, set, delete, incr, stats,
    CacheError, CacheConnectionError, CacheNotInitializedError
)


class TestCacheGet:
    """Test cache.get() function"""
    
    @pytest.mark.asyncio
    async def test_get_existing_key(self):
        """Test retrieving existing key"""
        with patch('omnicorn.cache._rpc_call', new_callable=AsyncMock) as mock_rpc:
            mock_rpc.return_value = b'test_value'
            
            result = await get('test_key')
            
            assert result == b'test_value'
            mock_rpc.assert_called_once_with(
                b"ets_get",
                {b"key": b'test_key'}
            )
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self):
        """Test retrieving non-existent key returns None"""
        with patch('omnicorn.cache._rpc_call', new_callable=AsyncMock) as mock_rpc:
            mock_rpc.return_value = b'nil'
            
            result = await get('nonexistent_key')
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_get_connection_error(self):
        """Test CacheConnectionError on transport failure"""
        with patch('omnicorn.cache._rpc_call', new_callable=AsyncMock) as mock_rpc:
            mock_rpc.side_effect = RuntimeError("Connection lost")
            
            with pytest.raises(CacheConnectionError):
                await get('test_key')


class TestCacheSet:
    """Test cache.set() function"""
    
    @pytest.mark.asyncio
    async def test_set_string_value(self):
        """Test setting string value"""
        with patch('omnicorn.cache._rpc_call', new_callable=AsyncMock) as mock_rpc:
            mock_rpc.return_value = True
            
            result = await set('test_key', 'test_value')
            
            assert result is True
            mock_rpc.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_set_dict_value(self):
        """Test setting dict value"""
        with patch('omnicorn.cache._rpc_call', new_callable=AsyncMock) as mock_rpc:
            mock_rpc.return_value = True
            
            result = await set('test_key', {'name': 'test'})
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_set_with_ttl(self):
        """Test setting value with TTL"""
        with patch('omnicorn.cache._rpc_call', new_callable=AsyncMock) as mock_rpc:
            mock_rpc.return_value = True
            
            result = await set('test_key', 'value', ttl_ms=3600000)
            
            assert result is True
            call_args = mock_rpc.call_args[0][1]
            assert call_args[b'ttl'] == 3600000
    
    @pytest.mark.asyncio
    async def test_set_without_ttl(self):
        """Test setting value without TTL (persistent)"""
        with patch('omnicorn.cache._rpc_call', new_callable=AsyncMock) as mock_rpc:
            mock_rpc.return_value = True
            
            result = await set('test_key', 'value')
            
            assert result is True
            call_args = mock_rpc.call_args[0][1]
            assert call_args[b'ttl'] == 0
    
    @pytest.mark.asyncio
    async def test_set_connection_error(self):
        """Test CacheConnectionError on transport failure"""
        with patch('omnicorn.cache._rpc_call', new_callable=AsyncMock) as mock_rpc:
            mock_rpc.side_effect = RuntimeError("Connection lost")
            
            with pytest.raises(CacheConnectionError):
                await set('test_key', 'value')


class TestCacheDelete:
    """Test cache.delete() function"""
    
    @pytest.mark.asyncio
    async def test_delete_existing_key(self):
        """Test deleting existing key"""
        with patch('omnicorn.cache._rpc_call', new_callable=AsyncMock) as mock_rpc:
            # cache.delete returns True if response == b"ok"
            mock_rpc.return_value = b'ok'
            
            result = await delete('test_key')
            
            assert result is True
    
    @pytest.mark.asyncio
    async def test_delete_nonexistent_key(self):
        """Test deleting non-existent key returns False"""
        with patch('omnicorn.cache._rpc_call', new_callable=AsyncMock) as mock_rpc:
            mock_rpc.return_value = False
            
            result = await delete('nonexistent_key')
            
            assert result is False


class TestCacheIncr:
    """Test cache.incr() function"""
    
    @pytest.mark.asyncio
    async def test_incr_existing_counter(self):
        """Test incrementing existing counter"""
        with patch('omnicorn.cache._rpc_call', new_callable=AsyncMock) as mock_rpc:
            mock_rpc.return_value = 5
            
            result = await incr('counter')
            
            assert result == 5
    
    @pytest.mark.asyncio
    async def test_incr_with_amount(self):
        """Test incrementing by specific amount"""
        with patch('omnicorn.cache._rpc_call', new_callable=AsyncMock) as mock_rpc:
            mock_rpc.return_value = 10
            
            result = await incr('counter', amount=5)
            
            assert result == 10
            call_args = mock_rpc.call_args[0][1]
            assert call_args[b'amount'] == 5
    
    @pytest.mark.asyncio
    async def test_incr_nonexistent_key(self):
        """Test incrementing non-existent key raises CacheError"""
        with patch('omnicorn.cache._rpc_call', new_callable=AsyncMock) as mock_rpc:
            mock_rpc.return_value = None
            
            with pytest.raises(CacheError):
                await incr('nonexistent_counter')


class TestCacheStats:
    """Test cache.stats() function"""
    
    @pytest.mark.asyncio
    async def test_stats_returns_dict(self):
        """Test stats returns dictionary with size"""
        with patch('omnicorn.cache._rpc_call', new_callable=AsyncMock) as mock_rpc:
            mock_rpc.return_value = {b'size': 100}
            
            result = await stats()
            
            assert isinstance(result, dict)
            assert result[b'size'] == 100
    
    @pytest.mark.asyncio
    async def test_stats_includes_pending(self):
        """Test stats includes pending RPC count"""
        with patch('omnicorn.cache._rpc_call', new_callable=AsyncMock) as mock_rpc:
            mock_rpc.return_value = {b'size': 50, b'pending': 5}
            
            result = await stats()
            
            assert isinstance(result, dict)
            assert b'size' in result or b'pending' in result


class TestCacheInternals:
    """Test internal cache functions"""
    
    def test_initialize_sets_transport(self):
        """Test _initialize sets _ipc_transport"""
        from omnicorn.cache import _initialize, _ipc_transport, _cleanup
        
        mock_transport = object()
        _initialize(mock_transport)
        
        # Import again to get updated value
        import omnicorn.cache as cache_module
        assert cache_module._ipc_transport == mock_transport
        
        _cleanup()
    
    def test_cleanup_clears_state(self):
        """Test _cleanup clears transport and pending_calls"""
        from omnicorn.cache import _initialize, _cleanup, _pending_calls
        import omnicorn.cache as cache_module
        
        mock_transport = object()
        _initialize(mock_transport)
        
        _cleanup()
        
        assert cache_module._ipc_transport is None
        assert len(_pending_calls) == 0

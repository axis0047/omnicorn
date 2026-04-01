"""
Protocol Test Suite - ETF encoding/decoding
Coverage Target: 100%
"""

import pytest
import asyncio
import struct
from unittest.mock import AsyncMock, MagicMock

from omnicorn.protocol import AsyncProtocol


class TestAsyncProtocolRead:
    """Test protocol reading"""
    
    @pytest.mark.asyncio
    async def test_read_valid_message(self):
        """Test reading valid ETF message"""
        # Create a mock reader
        mock_reader = AsyncMock()
        
        # Valid message: 4-byte header + payload
        payload = b'\x83a\x01'  # ETF encoded small integer
        header = struct.pack('>I', len(payload))
        
        mock_reader.readexactly = AsyncMock(side_effect=[header, payload])
        
        result = await AsyncProtocol.read(mock_reader)
        
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_read_incomplete_header(self):
        """Test handling incomplete header"""
        mock_reader = AsyncMock()
        mock_reader.readexactly = AsyncMock(
            side_effect=asyncio.IncompleteReadError(b'partial', 4)
        )
        
        result = await AsyncProtocol.read(mock_reader)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_read_incomplete_payload(self):
        """Test handling incomplete payload"""
        mock_reader = AsyncMock()
        
        payload = b'\x83a\x01'
        header = struct.pack('>I', len(payload))
        
        mock_reader.readexactly = AsyncMock(
            side_effect=[header, asyncio.IncompleteReadError(b'partial', len(payload))]
        )
        
        result = await AsyncProtocol.read(mock_reader)
        
        assert result is None
    
    @pytest.mark.asyncio
    async def test_read_corrupt_etf(self):
        """Test handling corrupt ETF data"""
        mock_reader = AsyncMock()
        
        # Valid header but corrupt payload
        corrupt_payload = b'\xff\xfe\xfd'
        header = struct.pack('>I', len(corrupt_payload))
        
        mock_reader.readexactly = AsyncMock(side_effect=[header, corrupt_payload])
        
        result = await AsyncProtocol.read(mock_reader)
        
        assert result is None


class TestAsyncProtocolWrite:
    """Test protocol writing"""
    
    @pytest.mark.asyncio
    async def test_write_valid_message(self):
        """Test writing valid ETF message"""
        mock_writer = AsyncMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        
        write_lock = asyncio.Lock()
        data = {b'type': b'test', b'data': b'value'}
        
        await AsyncProtocol.write(mock_writer, write_lock, data)
        
        mock_writer.write.assert_called_once()
        mock_writer.drain.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_write_with_lock(self):
        """Test write uses lock for thread safety"""
        mock_writer = AsyncMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        
        write_lock = asyncio.Lock()
        data = {b'type': b'test'}
        
        # Acquire lock first
        await write_lock.acquire()
        
        # Write should wait for lock
        async def release_later():
            await asyncio.sleep(0.1)
            write_lock.release()
        
        asyncio.create_task(release_later())
        
        await AsyncProtocol.write(mock_writer, write_lock, data)
        
        mock_writer.write.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_write_large_payload(self):
        """Test writing large payload"""
        mock_writer = AsyncMock()
        mock_writer.write = MagicMock()
        mock_writer.drain = AsyncMock()
        
        write_lock = asyncio.Lock()
        large_data = {b'data': b'x' * 1000000}  # 1MB payload
        
        await AsyncProtocol.write(mock_writer, write_lock, large_data)
        
        mock_writer.write.assert_called_once()
        mock_writer.drain.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_write_connection_error(self):
        """Test handling write connection error"""
        mock_writer = AsyncMock()
        mock_writer.write = MagicMock(side_effect=ConnectionError())
        mock_writer.drain = AsyncMock()
        
        write_lock = asyncio.Lock()
        data = {b'type': b'test'}
        
        # Should not raise, just log error
        await AsyncProtocol.write(mock_writer, write_lock, data)

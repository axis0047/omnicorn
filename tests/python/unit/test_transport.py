"""
Transport Test Suite
Coverage Target: 95%
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from omnicorn.transport import PyUDSTransport, OmniTransport


class TestOmniTransport:
    """Test abstract OmniTransport interface"""
    
    def test_omni_transport_is_abstract(self):
        """Test OmniTransport cannot be instantiated"""
        with pytest.raises(TypeError):
            OmniTransport()
    
    def test_omni_transport_requires_methods(self):
        """Test OmniTransport requires all abstract methods"""
        class IncompleteTransport(OmniTransport):
            async def connect(self):
                pass
        
        with pytest.raises(TypeError):
            IncompleteTransport()


class TestPyUDSTransport:
    """Test PyUDSTransport implementation"""
    
    @pytest.mark.asyncio
    async def test_connect_success(self):
        """Test successful connection to UDS"""
        with patch('asyncio.open_unix_connection') as mock_open:
            mock_reader = AsyncMock()
            mock_writer = AsyncMock()
            mock_open.return_value = (mock_reader, mock_writer)
            
            transport = PyUDSTransport('/tmp/test.sock')
            await transport.connect()
            
            assert transport._reader == mock_reader
            assert transport._writer == mock_writer
            mock_open.assert_called_once_with('/tmp/test.sock')
    
    @pytest.mark.asyncio
    async def test_connect_failure(self):
        """Test connection failure"""
        with patch('asyncio.open_unix_connection') as mock_open:
            mock_open.side_effect = ConnectionRefusedError()
            
            transport = PyUDSTransport('/tmp/nonexistent.sock')
            
            with pytest.raises(SystemExit):
                await transport.connect()
    
    @pytest.mark.asyncio
    async def test_send_success(self):
        """Test successful message send"""
        transport = PyUDSTransport('/tmp/test.sock')
        transport._writer = AsyncMock()
        transport._writer.write = MagicMock()
        transport._writer.drain = AsyncMock()
        transport._write_lock = asyncio.Lock()
        
        data = {b'type': b'test', b'data': b'value'}
        await transport.send(data)
        
        transport._writer.write.assert_called_once()
        transport._writer.drain.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_with_lock(self):
        """Test send uses lock for thread safety"""
        transport = PyUDSTransport('/tmp/test.sock')
        transport._writer = AsyncMock()
        transport._writer.write = MagicMock()
        transport._writer.drain = AsyncMock()
        transport._write_lock = asyncio.Lock()
        
        # Send multiple messages concurrently
        async def send_msg(i):
            await transport.send({b'id': i})
        
        await asyncio.gather(*[send_msg(i) for i in range(5)])
        
        assert transport._writer.write.call_count == 5
    
    @pytest.mark.asyncio
    async def test_send_error(self):
        """Test send error handling"""
        transport = PyUDSTransport('/tmp/test.sock')
        transport._writer = AsyncMock()
        transport._writer.write = MagicMock(side_effect=ConnectionError())
        transport._writer.drain = AsyncMock()
        transport._write_lock = asyncio.Lock()
        
        data = {b'type': b'test'}
        
        # Should not raise, just log error
        await transport.send(data)
    
    @pytest.mark.asyncio
    async def test_recv_success(self):
        """Test successful message receive"""
        transport = PyUDSTransport('/tmp/test.sock')
        
        with patch('omnicorn.protocol.AsyncProtocol.read') as mock_read:
            mock_read.return_value = {b'type': b'test', b'data': b'value'}
            transport._reader = AsyncMock()
            
            result = await transport.recv()
            
            assert result == {b'type': b'test', b'data': b'value'}
            mock_read.assert_called_once_with(transport._reader)
    
    @pytest.mark.asyncio
    async def test_recv_error(self):
        """Test receive error handling"""
        transport = PyUDSTransport('/tmp/test.sock')
        
        with patch('omnicorn.protocol.AsyncProtocol.read') as mock_read:
            mock_read.return_value = None
            transport._reader = AsyncMock()
            
            result = await transport.recv()
            
            assert result is None
    
    @pytest.mark.asyncio
    async def test_close_success(self):
        """Test successful close"""
        transport = PyUDSTransport('/tmp/test.sock')
        transport._writer = AsyncMock()
        transport._writer.close = MagicMock()
        transport._writer.wait_closed = AsyncMock()
        
        await transport.close()
        
        transport._writer.close.assert_called_once()
        transport._writer.wait_closed.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_close_no_writer(self):
        """Test close when no writer exists"""
        transport = PyUDSTransport('/tmp/test.sock')
        transport._writer = None
        
        # Should not raise
        await transport.close()
    
    @pytest.mark.asyncio
    async def test_full_roundtrip(self):
        """Test full send/recv roundtrip"""
        with patch('asyncio.open_unix_connection') as mock_open:
            mock_reader = AsyncMock()
            mock_writer = AsyncMock()
            mock_writer.write = MagicMock()
            mock_writer.drain = AsyncMock()
            mock_open.return_value = (mock_reader, mock_writer)
            
            transport = PyUDSTransport('/tmp/test.sock')
            await transport.connect()
            
            # Send
            await transport.send({b'type': b'test'})
            
            # Receive
            with patch('omnicorn.protocol.AsyncProtocol.read') as mock_read:
                mock_read.return_value = {b'type': b'reply'}
                result = await transport.recv()
                
                assert result == {b'type': b'reply'}
            
            await transport.close()

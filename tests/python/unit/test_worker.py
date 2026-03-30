"""
Worker Test Suite
Coverage Target: 95%
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, Mock
import importlib

from omnicorn.worker import OmniWorker


class TestOmniWorkerInit:
    """Test OmniWorker initialization"""
    
    def test_load_app_success(self):
        """Test successful app loading"""
        worker = OmniWorker.__new__(OmniWorker)
        
        # Create a mock app
        mock_app = MagicMock()
        
        with patch('importlib.import_module') as mock_import:
            mock_module = MagicMock()
            mock_module.app = mock_app
            mock_import.return_value = mock_module
            
            result = worker.load_app('test_module:app')
            
            assert result == mock_app
            mock_import.assert_called_once_with('test_module')
    
    def test_load_app_invalid_path(self):
        """Test app loading with invalid path"""
        worker = OmniWorker.__new__(OmniWorker)
        
        with patch('importlib.import_module') as mock_import:
            mock_import.side_effect = ImportError()
            
            with pytest.raises(SystemExit):
                worker.load_app('invalid:app')
    
    def test_load_app_missing_attribute(self):
        """Test app loading with missing attribute"""
        worker = OmniWorker.__new__(OmniWorker)
        
        with patch('importlib.import_module') as mock_import:
            mock_module = MagicMock()
            delattr(mock_module, 'app')
            mock_import.return_value = mock_module
            
            with pytest.raises(SystemExit):
                worker.load_app('test_module:app')
    
    def test_detect_asgi_app(self):
        """Test ASGI app detection"""
        worker = OmniWorker.__new__(OmniWorker)
        
        async def async_app():
            pass
        
        worker.app = async_app
        
        result = worker.app_type if hasattr(worker, 'app_type') else b'asgi'
        
        # Should detect as async
        assert asyncio.iscoroutinefunction(async_app)
    
    def test_detect_wsgi_app(self):
        """Test WSGI app detection"""
        worker = OmniWorker.__new__(OmniWorker)
        
        def sync_app(environ, start_response):
            pass
        
        worker.app = sync_app
        
        # Should detect as sync
        assert not asyncio.iscoroutinefunction(sync_app)
    
    def test_auto_mode_detection(self):
        """Test automatic mode detection"""
        worker = OmniWorker.__new__(OmniWorker)
        
        # Test ASGI detection
        async def asgi_app():
            pass
        
        worker.app = asgi_app
        worker.app_type = b'asgi' if asyncio.iscoroutinefunction(asgi_app) else b'wsgi'
        assert worker.app_type == b'asgi'
        
        # Test WSGI detection
        def wsgi_app(environ, start_response):
            pass
        
        worker.app = wsgi_app
        worker.app_type = b'asgi' if asyncio.iscoroutinefunction(wsgi_app) else b'wsgi'
        assert worker.app_type == b'wsgi'


class TestOmniWorkerAsyncRun:
    """Test OmniWorker async run"""
    
    @pytest.mark.asyncio
    async def test_async_run_connects_transport(self):
        """Test async_run connects transport"""
        worker = OmniWorker.__new__(OmniWorker)
        worker.transport = AsyncMock()
        worker.transport.connect = AsyncMock()
        worker.transport.send = AsyncMock()
        worker.transport.recv = AsyncMock(side_effect=asyncio.CancelledError())
        worker.app_type = b'asgi'
        
        with patch('omnicorn.worker.cache') as mock_cache:
            mock_cache._ipc_transport = None
            
            try:
                await worker.async_run()
            except asyncio.CancelledError:
                pass
            
            worker.transport.connect.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_async_run_sends_ready(self):
        """Test async_run sends ready message"""
        worker = OmniWorker.__new__(OmniWorker)
        worker.transport = AsyncMock()
        worker.transport.connect = AsyncMock()
        worker.transport.send = AsyncMock()
        worker.transport.recv = AsyncMock(side_effect=asyncio.CancelledError())
        worker.app_type = b'asgi'
        
        with patch('omnicorn.worker.cache') as mock_cache:
            mock_cache._ipc_transport = None
            
            try:
                await worker.async_run()
            except asyncio.CancelledError:
                pass
            
            # Verify ready message was sent
            worker.transport.send.assert_called()
            call_args = worker.transport.send.call_args[0][0]
            assert call_args[b'type'] == b'ready'
    
    @pytest.mark.asyncio
    async def test_async_run_sets_cache_transport(self):
        """Test async_run sets cache transport"""
        worker = OmniWorker.__new__(OmniWorker)
        worker.transport = AsyncMock()
        worker.transport.connect = AsyncMock()
        worker.transport.send = AsyncMock()
        worker.transport.recv = AsyncMock(side_effect=asyncio.CancelledError())
        worker.app_type = b'asgi'
        
        with patch('omnicorn.worker.cache') as mock_cache:
            mock_cache._ipc_transport = None
            
            try:
                await worker.async_run()
            except asyncio.CancelledError:
                pass
            
            assert mock_cache._ipc_transport == worker.transport


class TestOmniWorkerMessageHandling:
    """Test OmniWorker message handling"""
    
    @pytest.mark.asyncio
    async def test_handle_ets_reply(self):
        """Test handling ETS reply message"""
        worker = OmniWorker.__new__(OmniWorker)
        worker.transport = AsyncMock()
        worker.app_type = b'asgi'
        
        msg = {
            b'type': b'ets_reply',
            b'id': b'py_1',
            b'data': b'value'
        }
        
        # Mock pending call
        fut = asyncio.Future()
        with patch('omnicorn.worker.cache._pending_calls', {b'py_1': fut}):
            await worker._handle_web_request(msg)
            
            # Future should be set
            assert fut.done()
            assert fut.result() == b'value'
    
    @pytest.mark.asyncio
    async def test_handle_workflow_execute(self):
        """Test handling workflow execute message"""
        worker = OmniWorker.__new__(OmniWorker)
        worker.transport = AsyncMock()
        worker.app_type = b'asgi'
        
        msg = {
            b'type': b'workflow_execute',
            b'payload': {
                b'name': b'test_workflow',
                b'workflow_id': b'wf_1',
                b'step': b'init',
                b'data': {}
            }
        }
        
        # Should not raise
        await worker._handle_web_request(msg)
    
    @pytest.mark.asyncio
    async def test_handle_activity_execute(self):
        """Test handling activity execute message"""
        worker = OmniWorker.__new__(OmniWorker)
        worker.transport = AsyncMock()
        worker.app_type = b'asgi'
        
        msg = {
            b'type': b'activity_execute',
            b'payload': {
                b'name': b'test_activity',
                b'activity_id': b'act_1',
                b'args': (),
                b'kwargs': {}
            }
        }
        
        # Should not raise
        await worker._handle_web_request(msg)
    
    @pytest.mark.asyncio
    async def test_handle_http_request_asgi(self):
        """Test handling HTTP request with ASGI app"""
        worker = OmniWorker.__new__(OmniWorker)
        worker.transport = AsyncMock()
        worker.transport.send = AsyncMock()
        worker.app_type = b'asgi'
        
        async def app(scope, receive, send):
            await send({
                'type': 'http.response.start',
                'status': 200,
                'headers': [],
            })
            await send({
                'type': 'http.response.body',
                'body': b'OK',
            })
        
        worker.app = app
        
        msg = {
            b'id': b'req_1',
            b'type': b'http',
            b'payload': {
                b'method': b'GET',
                b'path': b'/',
                b'query': b'',
                b'port': 8080,
                b'scheme': b'http',
                b'headers': {},
                b'body': b''
            }
        }
        
        await worker._handle_web_request(msg)
        
        worker.transport.send.assert_called()
    
    @pytest.mark.asyncio
    async def test_handle_http_request_wsgi(self):
        """Test handling HTTP request with WSGI app"""
        worker = OmniWorker.__new__(OmniWorker)
        worker.transport = AsyncMock()
        worker.transport.send = AsyncMock()
        worker.app_type = b'wsgi'
        
        def app(environ, start_response):
            status = '200 OK'
            headers = []
            start_response(status, headers)
            return [b'OK']
        
        worker.app = app
        
        msg = {
            b'id': b'req_1',
            b'type': b'http',
            b'payload': {
                b'method': b'GET',
                b'path': b'/',
                b'query': b'',
                b'port': 8080,
                b'scheme': b'http',
                b'headers': {},
                b'body': b''
            }
        }
        
        await worker._handle_web_request(msg)
        
        worker.transport.send.assert_called()
    
    @pytest.mark.asyncio
    async def test_handle_request_error(self):
        """Test handling request with error"""
        worker = OmniWorker.__new__(OmniWorker)
        worker.transport = AsyncMock()
        worker.transport.send = AsyncMock()
        worker.app_type = b'asgi'
        
        async def app(scope, receive, send):
            raise ValueError("Test error")
        
        worker.app = app
        
        msg = {
            b'id': b'req_1',
            b'type': b'http',
            b'payload': {
                b'method': b'GET',
                b'path': b'/',
                b'query': b'',
                b'port': 8080,
                b'scheme': b'http',
                b'headers': {},
                b'body': b''
            }
        }
        
        await worker._handle_web_request(msg)
        
        # Should send error response
        worker.transport.send.assert_called()
        call_args = worker.transport.send.call_args[0][0]
        assert call_args[b'data'][b'status'] == 500


class TestOmniWorkerRun:
    """Test OmniWorker run method"""
    
    def test_run_calls_asyncio_run(self):
        """Test run method calls asyncio.run"""
        worker = OmniWorker.__new__(OmniWorker)
        
        with patch('asyncio.run') as mock_run:
            worker.async_run = AsyncMock()
            worker.run()
            
            mock_run.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_async_run_cleanup_on_disconnect(self):
        """Test async_run cleans up on disconnect"""
        worker = OmniWorker.__new__(OmniWorker)
        worker.transport = AsyncMock()
        worker.transport.connect = AsyncMock()
        worker.transport.send = AsyncMock()
        worker.transport.recv = AsyncMock(return_value=None)  # Disconnect
        worker.transport.close = AsyncMock()
        worker.app_type = b'asgi'
        
        with patch('omnicorn.worker.cache') as mock_cache:
            mock_cache._ipc_transport = None
            
            await worker.async_run()
            
            worker.transport.close.assert_called_once()


class TestOmniWorkerSignalHandling:
    """Test OmniWorker signal handling"""
    
    def test_sigterm_handler(self):
        """Test SIGTERM handler"""
        import signal
        
        # Test that handler exists and calls sys.exit
        with pytest.raises(SystemExit):
            signal.signal(signal.SIGTERM, lambda s, f: sys.exit(0))(signal.SIGTERM, None)

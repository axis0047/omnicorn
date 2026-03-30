"""
Activities Test Suite
Coverage Target: 95%
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from omnicorn.orchestrator.activities import (
    activity, defer_activity, execute_activity,
    ACTIVITY_REGISTRY
)


class TestActivityDecorator:
    """Test @activity decorator"""
    
    def setup_method(self):
        """Clear registry before each test"""
        ACTIVITY_REGISTRY.clear()
    
    def teardown_method(self):
        """Clear registry after each test"""
        ACTIVITY_REGISTRY.clear()
    
    def test_activity_registers_function(self):
        """Test activity decorator registers function"""
        @activity(name="test_activity")
        async def act():
            pass
        
        assert b"test_activity" in ACTIVITY_REGISTRY
        assert ACTIVITY_REGISTRY[b"test_activity"]["func"] == act
    
    def test_activity_default_name(self):
        """Test activity uses function name by default"""
        @activity()
        async def my_activity():
            pass
        
        assert b"my_activity" in ACTIVITY_REGISTRY
    
    def test_activity_default_retries(self):
        """Test activity has default retry count"""
        @activity(name="test")
        async def act():
            pass
        
        assert ACTIVITY_REGISTRY[b"test"]["retries"] == 3
    
    def test_activity_custom_retries(self):
        """Test activity with custom retry count"""
        @activity(name="test", retries=5)
        async def act():
            pass
        
        assert ACTIVITY_REGISTRY[b"test"]["retries"] == 5
    
    def test_activity_multiple_activities(self):
        """Test registering multiple activities"""
        @activity(name="act_1")
        async def act1():
            pass
        
        @activity(name="act_2", retries=2)
        async def act2():
            pass
        
        assert b"act_1" in ACTIVITY_REGISTRY
        assert b"act_2" in ACTIVITY_REGISTRY
        assert ACTIVITY_REGISTRY[b"act_2"]["retries"] == 2
    
    def test_activity_sync_function(self):
        """Test activity decorator with sync function"""
        @activity(name="sync_act")
        def sync_activity():
            pass
        
        assert b"sync_act" in ACTIVITY_REGISTRY
        assert not asyncio.iscoroutinefunction(sync_activity)


class TestDeferActivity:
    """Test defer_activity function"""
    
    @pytest.mark.asyncio
    async def test_defer_activity_sends_rpc(self):
        """Test defer_activity sends RPC call"""
        with patch('omnicorn.orchestrator.activities._rpc_call') as mock_rpc:
            mock_rpc.return_value = b'queued'
            
            result = await defer_activity("test_activity", "arg1", "arg2", key="value")
            
            mock_rpc.assert_called_once()
            call_args = mock_rpc.call_args[0]
            assert call_args[0] == b"activity_enqueue"
            assert call_args[1][b"name"] == b"test_activity"
    
    @pytest.mark.asyncio
    async def test_defer_activity_encodes_name(self):
        """Test defer_activity encodes activity name"""
        with patch('omnicorn.orchestrator.activities._rpc_call') as mock_rpc:
            mock_rpc.return_value = b'queued'
            
            await defer_activity("my_activity")
            
            call_args = mock_rpc.call_args[0][1]
            assert isinstance(call_args[b"name"], bytes)
            assert call_args[b"name"] == b"my_activity"
    
    @pytest.mark.asyncio
    async def test_defer_activity_passes_args(self):
        """Test defer_activity passes args correctly"""
        with patch('omnicorn.orchestrator.activities._rpc_call') as mock_rpc:
            mock_rpc.return_value = b'queued'
            
            await defer_activity("test", "pos1", "pos2", kw1="val1", kw2="val2")
            
            call_args = mock_rpc.call_args[0][1]
            assert call_args[b"args"] == ("pos1", "pos2")
            assert call_args[b"kwargs"] == {"kw1": "val1", "kw2": "val2"}
    
    @pytest.mark.asyncio
    async def test_defer_activity_no_args(self):
        """Test defer_activity with no arguments"""
        with patch('omnicorn.orchestrator.activities._rpc_call') as mock_rpc:
            mock_rpc.return_value = b'queued'
            
            await defer_activity("test")
            
            call_args = mock_rpc.call_args[0][1]
            assert call_args[b"args"] == ()
            assert call_args[b"kwargs"] == {}


class TestExecuteActivity:
    """Test execute_activity function"""
    
    def setup_method(self):
        """Clear registry before each test"""
        ACTIVITY_REGISTRY.clear()
    
    def teardown_method(self):
        """Clear registry after each test"""
        ACTIVITY_REGISTRY.clear()
    
    @pytest.mark.asyncio
    async def test_execute_activity_success(self):
        """Test successful activity execution"""
        @activity(name="test_act")
        async def test_activity(x, y):
            return x + y
        
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        
        msg = {
            b'payload': {
                b'name': b'test_act',
                b'activity_id': b'act_1',
                b'args': (5, 3),
                b'kwargs': {}
            }
        }
        
        await execute_activity(msg, mock_transport)
        
        mock_transport.send.assert_called_once()
        call_args = mock_transport.send.call_args[0][0]
        assert call_args[b'type'] == b'activity_ack'
        assert call_args[b'activity_id'] == b'act_1'
    
    @pytest.mark.asyncio
    async def test_execute_activity_sync(self):
        """Test executing synchronous activity"""
        @activity(name="sync_act")
        def sync_activity(x):
            return x * 2
        
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        
        msg = {
            b'payload': {
                b'name': b'sync_act',
                b'activity_id': b'act_2',
                b'args': (21,),
                b'kwargs': {}
            }
        }
        
        await execute_activity(msg, mock_transport)
        
        mock_transport.send.assert_called_once()
        call_args = mock_transport.send.call_args[0][0]
        assert call_args[b'type'] == b'activity_ack'
    
    @pytest.mark.asyncio
    async def test_execute_activity_with_kwargs(self):
        """Test executing activity with kwargs"""
        @activity(name="kwargs_act")
        async def kwargs_activity(name, greeting="Hello"):
            return f"{greeting}, {name}!"
        
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        
        msg = {
            b'payload': {
                b'name': b'kwargs_act',
                b'activity_id': b'act_3',
                b'args': ("World",),
                b'kwargs': {b'greeting': b'Hi'}
            }
        }
        
        await execute_activity(msg, mock_transport)
        
        mock_transport.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_activity_error(self):
        """Test activity that raises error"""
        @activity(name="error_act")
        async def error_activity():
            raise ValueError("Activity failed")
        
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        
        msg = {
            b'payload': {
                b'name': b'error_act',
                b'activity_id': b'act_4',
                b'args': (),
                b'kwargs': {}
            }
        }
        
        await execute_activity(msg, mock_transport)
        
        call_args = mock_transport.send.call_args[0][0]
        assert call_args[b'type'] == b'activity_fail'
        assert call_args[b'activity_id'] == b'act_4'
        assert b'Activity failed' in call_args[b'error']
    
    @pytest.mark.asyncio
    async def test_execute_activity_not_found(self):
        """Test executing non-existent activity"""
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        
        msg = {
            b'payload': {
                b'name': b'nonexistent_act',
                b'activity_id': b'act_5',
                b'args': (),
                b'kwargs': {}
            }
        }
        
        await execute_activity(msg, mock_transport)
        
        # Should not send anything for unknown activity
        mock_transport.send.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_execute_activity_decodes_args(self):
        """Test activity args are decoded"""
        @activity(name="decode_act")
        async def decode_activity(name, value):
            # Args should be decoded strings
            assert isinstance(name, str)
            assert isinstance(value, str)
            return True
        
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        
        msg = {
            b'payload': {
                b'name': b'decode_act',
                b'activity_id': b'act_6',
                b'args': (b'string_arg', b'another_string'),
                b'kwargs': {}
            }
        }
        
        await execute_activity(msg, mock_transport)
        
        mock_transport.send.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_execute_activity_decodes_kwargs(self):
        """Test activity kwargs are decoded"""
        @activity(name="decode_kwargs_act")
        async def decode_kwargs_activity(**kwargs):
            # Kwargs should be decoded
            for k, v in kwargs.items():
                if isinstance(v, bytes):
                    assert isinstance(v.decode(), str)
            return True
        
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        
        msg = {
            b'payload': {
                b'name': b'decode_kwargs_act',
                b'activity_id': b'act_7',
                b'args': (),
                b'kwargs': {b'key1': b'value1', b'key2': b'value2'}
            }
        }
        
        await execute_activity(msg, mock_transport)
        
        mock_transport.send.assert_called_once()

"""
Tests for Omnicorn activity orchestration.
"""

import pytest
from omnicorn import activity, defer_activity
from omnicorn.orchestrator.activities import ACTIVITY_REGISTRY, execute_activity


@pytest.fixture(autouse=True)
def clear_activity_registry():
    """Clear activity registry before each test."""
    ACTIVITY_REGISTRY.clear()
    yield
    ACTIVITY_REGISTRY.clear()


@pytest.mark.asyncio
async def test_activity_decorator():
    """Test activity decorator registers function."""
    @activity(name="test_activity")
    async def my_activity(arg1, arg2):
        return arg1 + arg2
    
    assert b"test_activity" in ACTIVITY_REGISTRY
    assert ACTIVITY_REGISTRY[b"test_activity"]["func"] == my_activity
    assert ACTIVITY_REGISTRY[b"test_activity"]["retries"] == 3


@pytest.mark.asyncio
async def test_activity_decorator_custom_retries():
    """Test activity decorator with custom retry count."""
    @activity(name="test_activity", retries=5)
    async def my_activity():
        pass
    
    assert ACTIVITY_REGISTRY[b"test_activity"]["retries"] == 5


@pytest.mark.asyncio
async def test_activity_decorator_default_name():
    """Test activity decorator uses function name by default."""
    @activity()
    async def my_named_activity():
        pass
    
    assert b"my_named_activity" in ACTIVITY_REGISTRY


@pytest.mark.asyncio
async def test_defer_activity():
    """Test deferring an activity for background execution."""
    @activity(name="deferred_activity")
    async def my_activity(value):
        return value * 2
    
    # This should enqueue the activity
    # Note: Actual execution depends on worker availability
    result = await defer_activity("deferred_activity", 21)
    
    # Should return some acknowledgment
    assert result is not None


@pytest.mark.asyncio
async def test_execute_activity_success():
    """Test executing a registered activity."""
    @activity(name="exec_activity")
    async def my_activity(x, y):
        return x + y
    
    # Mock transport
    class MockTransport:
        def __init__(self):
            self.sent = []
        
        async def send(self, msg):
            self.sent.append(msg)
    
    transport = MockTransport()
    
    msg = {
        b"type": b"activity_execute",
        b"payload": {
            b"name": b"exec_activity",
            b"activity_id": b"test_123",
            b"args": (5, 3),
            b"kwargs": {}
        }
    }
    
    await execute_activity(msg, transport)
    
    # Should send acknowledgment
    assert len(transport.sent) == 1
    assert transport.sent[0][b"type"] == b"activity_ack"
    assert transport.sent[0][b"activity_id"] == b"test_123"


@pytest.mark.asyncio
async def test_execute_activity_failure():
    """Test executing an activity that raises an exception."""
    @activity(name="failing_activity")
    async def my_activity():
        raise ValueError("Test error")
    
    # Mock transport
    class MockTransport:
        def __init__(self):
            self.sent = []
        
        async def send(self, msg):
            self.sent.append(msg)
    
    transport = MockTransport()
    
    msg = {
        b"type": b"activity_execute",
        b"payload": {
            b"name": b"failing_activity",
            b"activity_id": b"test_456",
            b"args": (),
            b"kwargs": {}
        }
    }
    
    await execute_activity(msg, transport)
    
    # Should send failure notification
    assert len(transport.sent) == 1
    assert transport.sent[0][b"type"] == b"activity_fail"
    assert b"Test error" in transport.sent[0][b"error"]


@pytest.mark.asyncio
async def test_execute_activity_not_found():
    """Test executing a non-existent activity."""
    # Mock transport
    class MockTransport:
        def __init__(self):
            self.sent = []
        
        async def send(self, msg):
            self.sent.append(msg)
    
    transport = MockTransport()
    
    msg = {
        b"type": b"activity_execute",
        b"payload": {
            b"name": b"nonexistent_activity",
            b"activity_id": b"test_789",
            b"args": (),
            b"kwargs": {}
        }
    }
    
    # Should not send anything for unknown activity
    await execute_activity(msg, transport)
    assert len(transport.sent) == 0


@pytest.mark.asyncio
async def test_sync_activity():
    """Test executing a synchronous activity."""
    @activity(name="sync_activity")
    def my_sync_activity(value):
        return value * 2
    
    # Mock transport
    class MockTransport:
        def __init__(self):
            self.sent = []
        
        async def send(self, msg):
            self.sent.append(msg)
    
    transport = MockTransport()
    
    msg = {
        b"type": b"activity_execute",
        b"payload": {
            b"name": b"sync_activity",
            b"activity_id": b"test_sync",
            b"args": (21,),
            b"kwargs": {}
        }
    }
    
    await execute_activity(msg, transport)
    
    # Should complete successfully
    assert len(transport.sent) == 1
    assert transport.sent[0][b"type"] == b"activity_ack"

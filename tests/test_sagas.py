"""
Tests for Omnicorn workflow orchestration (sagas).
"""

import pytest
from omnicorn import orchestrator, start_workflow
from omnicorn.orchestrator.sagas import ORCHESTRATOR_REGISTRY, execute_workflow_step
from omnicorn.orchestrator.context import Context


@pytest.fixture(autouse=True)
def clear_orchestrator_registry():
    """Clear orchestrator registry before each test."""
    ORCHESTRATOR_REGISTRY.clear()
    yield
    ORCHESTRATOR_REGISTRY.clear()


@pytest.mark.asyncio
async def test_orchestrator_decorator():
    """Test orchestrator decorator registers workflow."""
    @orchestrator(name="test_workflow")
    async def my_workflow(ctx):
        return ctx.finish()
    
    assert b"test_workflow" in ORCHESTRATOR_REGISTRY
    assert ORCHESTRATOR_REGISTRY[b"test_workflow"] == my_workflow


@pytest.mark.asyncio
async def test_context_checkpoint():
    """Test Context.checkpoint() method."""
    ctx = Context(b"wf_123", b"step_one", {b"data": b"value"})
    
    result = ctx.checkpoint("next_step", sleep_ms=1000)
    
    assert result[b"type"] == b"workflow_checkpoint"
    assert result[b"workflow_id"] == b"wf_123"
    assert result[b"next_step"] == b"next_step"
    assert result[b"sleep_ms"] == 1000
    assert result[b"data"] == {"data": "value"}


@pytest.mark.asyncio
async def test_context_checkpoint_with_sleep_variants():
    """Test Context.checkpoint() with different sleep units."""
    ctx = Context(b"wf_123", b"step", {})
    
    # Test seconds
    result = ctx.checkpoint("next", sleep_seconds=5)
    assert result[b"sleep_ms"] == 5000
    
    # Test days
    result = ctx.checkpoint("next", sleep_days=1)
    assert result[b"sleep_ms"] == 86400000
    
    # Test combined
    result = ctx.checkpoint("next", sleep_ms=500, sleep_seconds=2)
    assert result[b"sleep_ms"] == 2500


@pytest.mark.asyncio
async def test_context_finish():
    """Test Context.finish() method."""
    ctx = Context(b"wf_123", b"final_step", {})
    
    result = ctx.finish()
    
    assert result[b"type"] == b"workflow_checkpoint"
    assert result[b"next_step"] == b"__finished__"


@pytest.mark.asyncio
async def test_context_data_decoding():
    """Test that Context properly decodes byte data."""
    ctx = Context(
        b"wf_123",
        b"step",
        {b"string_key": b"string_value", b"number": 42}
    )
    
    # Keys and values should be decoded to strings
    assert "string_key" in ctx.data
    assert ctx.data["string_key"] == "string_value"
    assert ctx.data["number"] == 42


@pytest.mark.asyncio
async def test_execute_workflow_step():
    """Test executing a workflow step."""
    @orchestrator(name="test_exec_workflow")
    async def my_workflow(ctx):
        if ctx.step == "init":
            return ctx.checkpoint("step_two", sleep_ms=0)
        elif ctx.step == "step_two":
            return ctx.finish()
    
    # Mock transport
    class MockTransport:
        def __init__(self):
            self.sent = []
        
        async def send(self, msg):
            self.sent.append(msg)
    
    transport = MockTransport()
    
    msg = {
        b"type": b"workflow_execute",
        b"payload": {
            b"name": b"test_exec_workflow",
            b"workflow_id": b"wf_test",
            b"step": b"init",
            b"data": {}
        }
    }
    
    await execute_workflow_step(msg, transport)
    
    # Should send checkpoint command
    assert len(transport.sent) == 1
    assert transport.sent[0][b"type"] == b"workflow_checkpoint"


@pytest.mark.asyncio
async def test_execute_workflow_step_not_found():
    """Test executing a non-existent workflow."""
    # Mock transport
    class MockTransport:
        def __init__(self):
            self.sent = []
        
        async def send(self, msg):
            self.sent.append(msg)
    
    transport = MockTransport()
    
    msg = {
        b"type": b"workflow_execute",
        b"payload": {
            b"name": b"nonexistent_workflow",
            b"workflow_id": b"wf_test",
            b"step": b"init",
            b"data": {}
        }
    }
    
    await execute_workflow_step(msg, transport)
    
    # Should send error
    assert len(transport.sent) == 1
    assert transport.sent[0][b"type"] == b"workflow_error"
    assert b"Saga Not Found" in transport.sent[0][b"error"]


@pytest.mark.asyncio
async def test_execute_workflow_step_error():
    """Test workflow step that raises an exception."""
    @orchestrator(name="error_workflow")
    async def my_workflow(ctx):
        raise ValueError("Workflow error")
    
    # Mock transport
    class MockTransport:
        def __init__(self):
            self.sent = []
        
        async def send(self, msg):
            self.sent.append(msg)
    
    transport = MockTransport()
    
    msg = {
        b"type": b"workflow_execute",
        b"payload": {
            b"name": b"error_workflow",
            b"workflow_id": b"wf_test",
            b"step": b"init",
            b"data": {}
        }
    }
    
    await execute_workflow_step(msg, transport)
    
    # Should send error
    assert len(transport.sent) == 1
    assert transport.sent[0][b"type"] == b"workflow_error"


@pytest.mark.asyncio
async def test_start_workflow():
    """Test starting a workflow."""
    @orchestrator(name="start_test_workflow")
    async def my_workflow(ctx):
        return ctx.finish()
    
    # Note: This test requires a running worker and transport
    # In a real scenario, this would send a message to Erlang
    # For now, we just verify it doesn't crash
    try:
        result = await start_workflow(
            "start_test_workflow",
            "wf_start_test",
            init_data={"test": "data"}
        )
        # Should return some response from Erlang
        assert result is not None
    except Exception as e:
        # Expected if no worker is available
        # The error should be related to transport, not the function itself
        assert "transport" in str(e).lower() or "not initialized" in str(e).lower()

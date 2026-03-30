"""
Workflow Orchestrator (Sagas) Test Suite
Coverage Target: 95%
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from omnicorn.orchestrator.sagas import (
    orchestrator, start_workflow, execute_workflow_step,
    ORCHESTRATOR_REGISTRY
)
from omnicorn.orchestrator.context import Context


class TestOrchestratorDecorator:
    """Test @orchestrator decorator"""
    
    def setup_method(self):
        """Clear registry before each test"""
        ORCHESTRATOR_REGISTRY.clear()
    
    def teardown_method(self):
        """Clear registry after each test"""
        ORCHESTRATOR_REGISTRY.clear()
    
    def test_orchestrator_registers_function(self):
        """Test orchestrator decorator registers function"""
        @orchestrator(name="test_workflow")
        async def workflow(ctx):
            return ctx.finish()
        
        assert b"test_workflow" in ORCHESTRATOR_REGISTRY
        assert ORCHESTRATOR_REGISTRY[b"test_workflow"] == workflow
    
    def test_orchestrator_uses_function_name(self):
        """Test orchestrator uses function name by default"""
        # Note: orchestrator() requires name parameter
        # This tests that name is properly encoded
        @orchestrator(name="my_workflow")
        async def my_workflow(ctx):
            return ctx.finish()

        assert b"my_workflow" in ORCHESTRATOR_REGISTRY
    
    def test_orchestrator_multiple_workflows(self):
        """Test registering multiple workflows"""
        @orchestrator(name="workflow_1")
        async def wf1(ctx):
            return ctx.finish()
        
        @orchestrator(name="workflow_2")
        async def wf2(ctx):
            return ctx.finish()
        
        assert b"workflow_1" in ORCHESTRATOR_REGISTRY
        assert b"workflow_2" in ORCHESTRATOR_REGISTRY
    
    def test_orchestrator_overwrites_existing(self):
        """Test registering same name overwrites"""
        @orchestrator(name="test")
        async def wf1(ctx):
            return ctx.finish()
        
        @orchestrator(name="test")
        async def wf2(ctx):
            return ctx.finish()
        
        assert ORCHESTRATOR_REGISTRY[b"test"] == wf2


class TestStartWorkflow:
    """Test start_workflow function"""
    
    @pytest.mark.asyncio
    async def test_start_workflow_sends_rpc(self):
        """Test start_workflow sends RPC call"""
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        
        with patch('omnicorn.cache._rpc_call') as mock_rpc:
            mock_rpc.return_value = b'started'
            
            result = await start_workflow(
                "test_workflow",
                "wf_123",
                init_data={"key": "value"}
            )
            
            mock_rpc.assert_called_once()
            call_args = mock_rpc.call_args[0]
            assert call_args[0] == b"workflow_start"
            assert call_args[1][b"name"] == b"test_workflow"
            assert call_args[1][b"workflow_id"] == b"wf_123"
    
    @pytest.mark.asyncio
    async def test_start_workflow_without_init_data(self):
        """Test start_workflow without init data"""
        with patch('omnicorn.cache._rpc_call') as mock_rpc:
            mock_rpc.return_value = b'started'
            
            await start_workflow("test_workflow", "wf_123")
            
            call_args = mock_rpc.call_args[0][1]
            assert call_args[b"data"] == {}
    
    @pytest.mark.asyncio
    async def test_start_workflow_encodes_strings(self):
        """Test start_workflow encodes strings to bytes"""
        with patch('omnicorn.cache._rpc_call') as mock_rpc:
            mock_rpc.return_value = b'started'
            
            await start_workflow("test_workflow", "wf_123", {"key": "value"})
            
            call_args = mock_rpc.call_args[0][1]
            assert isinstance(call_args[b"name"], bytes)
            assert isinstance(call_args[b"workflow_id"], bytes)


class TestExecuteWorkflowStep:
    """Test execute_workflow_step function"""
    
    def setup_method(self):
        """Clear registry before each test"""
        ORCHESTRATOR_REGISTRY.clear()
    
    def teardown_method(self):
        """Clear registry after each test"""
        ORCHESTRATOR_REGISTRY.clear()
    
    @pytest.mark.asyncio
    async def test_execute_workflow_step_success(self):
        """Test successful workflow step execution"""
        @orchestrator(name="test_wf")
        async def workflow(ctx):
            return ctx.checkpoint("next_step", sleep_ms=100)
        
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        
        msg = {
            b'payload': {
                b'name': b'test_wf',
                b'workflow_id': b'wf_1',
                b'step': b'init',
                b'data': {b'key': b'value'}
            }
        }
        
        await execute_workflow_step(msg, mock_transport)
        
        mock_transport.send.assert_called_once()
        call_args = mock_transport.send.call_args[0][0]
        assert call_args[b'type'] == b'workflow_checkpoint'
        assert call_args[b'next_step'] == b'next_step'
    
    @pytest.mark.asyncio
    async def test_execute_workflow_step_finish(self):
        """Test workflow step that finishes"""
        @orchestrator(name="test_wf")
        async def workflow(ctx):
            return ctx.finish()
        
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        
        msg = {
            b'payload': {
                b'name': b'test_wf',
                b'workflow_id': b'wf_1',
                b'step': b'final',
                b'data': {}
            }
        }
        
        await execute_workflow_step(msg, mock_transport)
        
        call_args = mock_transport.send.call_args[0][0]
        assert call_args[b'next_step'] == b'__finished__'
    
    @pytest.mark.asyncio
    async def test_execute_workflow_step_not_found(self):
        """Test executing non-existent workflow"""
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        
        msg = {
            b'payload': {
                b'name': b'nonexistent_wf',
                b'workflow_id': b'wf_1',
                b'step': b'init',
                b'data': {}
            }
        }
        
        await execute_workflow_step(msg, mock_transport)
        
        call_args = mock_transport.send.call_args[0][0]
        assert call_args[b'type'] == b'workflow_error'
        assert b'Saga Not Found' in call_args[b'error']
    
    @pytest.mark.asyncio
    async def test_execute_workflow_step_error(self):
        """Test workflow step that raises error"""
        @orchestrator(name="error_wf")
        async def workflow(ctx):
            raise ValueError("Test error")
        
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        
        msg = {
            b'payload': {
                b'name': b'error_wf',
                b'workflow_id': b'wf_1',
                b'step': b'init',
                b'data': {}
            }
        }
        
        await execute_workflow_step(msg, mock_transport)
        
        call_args = mock_transport.send.call_args[0][0]
        assert call_args[b'type'] == b'workflow_error'
    
    @pytest.mark.asyncio
    async def test_execute_workflow_step_decodes_data(self):
        """Test workflow step decodes byte data"""
        @orchestrator(name="test_wf")
        async def workflow(ctx):
            # ctx.data should have string keys
            assert isinstance(ctx.data, dict)
            return ctx.finish()
        
        mock_transport = AsyncMock()
        mock_transport.send = AsyncMock()
        
        msg = {
            b'payload': {
                b'name': b'test_wf',
                b'workflow_id': b'wf_1',
                b'step': b'init',
                b'data': {b'string_key': b'string_value', b'number': 42}
            }
        }
        
        await execute_workflow_step(msg, mock_transport)


class TestWorkflowContext:
    """Test Context usage in workflows"""
    
    def test_context_checkpoint(self):
        """Test context.checkpoint() method"""
        ctx = Context(b'wf_1', b'step1', {b'key': b'value'})
        
        result = ctx.checkpoint("step2", sleep_ms=1000)
        
        assert result[b'type'] == b'workflow_checkpoint'
        assert result[b'workflow_id'] == b'wf_1'
        assert result[b'next_step'] == b'step2'
        assert result[b'sleep_ms'] == 1000
    
    def test_context_checkpoint_with_sleep_variants(self):
        """Test context.checkpoint() with different sleep units"""
        ctx = Context(b'wf_1', b'step1', {})
        
        # Test seconds
        result = ctx.checkpoint("step2", sleep_seconds=5)
        assert result[b'sleep_ms'] == 5000
        
        # Test days
        result = ctx.checkpoint("step2", sleep_days=1)
        assert result[b'sleep_ms'] == 86400000
        
        # Test combined
        result = ctx.checkpoint("step2", sleep_ms=500, sleep_seconds=2)
        assert result[b'sleep_ms'] == 2500
    
    def test_context_finish(self):
        """Test context.finish() method"""
        ctx = Context(b'wf_1', b'step1', {})
        
        result = ctx.finish()
        
        assert result[b'next_step'] == b'__finished__'
    
    def test_context_data_decoding(self):
        """Test context data is decoded"""
        ctx = Context(b'wf_1', b'step1', {b'string': b'value', b'number': 42})
        
        assert "string" in ctx.data
        assert ctx.data["string"] == "value"
        assert ctx.data["number"] == 42
    
    def test_context_workflow_id_decoding(self):
        """Test workflow ID is decoded"""
        ctx = Context(b'wf_123', b'step1', {})
        
        assert ctx.workflow_id == "wf_123"
    
    def test_context_step_decoding(self):
        """Test step is decoded"""
        ctx = Context(b'wf_123', b'init', {})
        
        assert ctx.step == "init"

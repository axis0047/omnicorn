"""
Fixtures for Omnicorn tests
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_transport():
    """Create a mock IPC transport"""
    transport = AsyncMock()
    transport.send = AsyncMock()
    transport.recv = AsyncMock()
    transport.connect = AsyncMock()
    transport.close = AsyncMock()
    return transport


@pytest.fixture
def mock_rpc_response():
    """Fixture for mocking RPC responses"""
    async def _mock_rpc(return_value):
        async def mock_call(*args, **kwargs):
            return return_value
        return mock_call
    return _mock_rpc


@pytest.fixture
async def async_mock():
    """Create an async mock"""
    return AsyncMock()


@pytest.fixture
def sample_cache_data():
    """Sample cache test data"""
    return {
        'string_key': 'string_value',
        'int_key': 42,
        'float_key': 3.14,
        'dict_key': {'nested': 'value'},
        'list_key': [1, 2, 3]
    }


@pytest.fixture
def sample_workflow_data():
    """Sample workflow test data"""
    return {
        'workflow_id': 'wf_123',
        'name': 'test_workflow',
        'step': 'init',
        'data': {'user_id': 'user_123', 'email': 'test@example.com'}
    }


@pytest.fixture
def sample_activity_data():
    """Sample activity test data"""
    return {
        'activity_id': 'act_123',
        'name': 'test_activity',
        'args': ('arg1', 'arg2'),
        'kwargs': {'key': 'value'}
    }

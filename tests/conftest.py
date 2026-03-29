"""
Pytest configuration and fixtures for Omnicorn tests.
"""

import asyncio
import os
import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_workflow_data():
    """Sample workflow data for testing."""
    return {
        "user_id": "user_123",
        "email": "test@example.com",
        "amount": 99.99,
    }


@pytest.fixture
def sample_cache_key():
    """Sample cache key for testing."""
    return "test:key"


@pytest.fixture
def sample_cache_value():
    """Sample cache value for testing."""
    return {"data": "test_value", "count": 42}

"""
Integration tests for Omnicorn.

These tests verify end-to-end functionality of the complete system.
Note: These tests require a running Omnicorn server.
"""

import asyncio
import os
import pytest
import subprocess
import time
import signal

import httpx


# Skip integration tests if OMNICORN_INTEGRATION_TEST is not set
pytestmark = pytest.mark.skipif(
    not os.environ.get('OMNICORN_INTEGRATION_TEST'),
    reason="Set OMNICORN_INTEGRATION_TEST=1 to run integration tests"
)


@pytest.fixture(scope="session")
def omnicorn_server():
    """Start an Omnicorn server for integration testing."""
    
    # Start server
    env = os.environ.copy()
    env['OMNICORN_PORT'] = '8765'
    env['OMNICORN_WORKERS'] = '2'
    
    proc = subprocess.Popen(
        ['omnicorn', 'examples.fastapi_app:app', '--config', '.omnicorn.dev.yaml'],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    
    # Wait for server to start
    time.sleep(3)
    
    yield 'http://127.0.0.1:8765'
    
    # Cleanup
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.mark.asyncio
async def test_http_get(omnicorn_server):
    """Test basic HTTP GET request."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{omnicorn_server}/")
        assert response.status_code == 200
        data = response.json()
        assert 'message' in data
        assert data['message'] == 'Hello from Omnicorn!'


@pytest.mark.asyncio
async def test_health_endpoint(omnicorn_server):
    """Test health check endpoint."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{omnicorn_server}/health")
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'healthy'


@pytest.mark.asyncio
async def test_concurrent_requests(omnicorn_server):
    """Test handling multiple concurrent requests."""
    async with httpx.AsyncClient() as client:
        tasks = [
            client.get(f"{omnicorn_server}/")
            for _ in range(10)
        ]
        responses = await asyncio.gather(*tasks)
        
        for response in responses:
            assert response.status_code == 200


@pytest.mark.asyncio
async def test_404_handling(omnicorn_server):
    """Test 404 handling for non-existent routes."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{omnicorn_server}/nonexistent")
        assert response.status_code == 404


@pytest.mark.asyncio
async def test_request_headers(omnicorn_server):
    """Test request header handling."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{omnicorn_server}/",
            headers={'X-Custom-Header': 'test-value'}
        )
        assert response.status_code == 200


@pytest.mark.asyncio
async def test_response_time(omnicorn_server):
    """Test response time is reasonable."""
    async with httpx.AsyncClient() as client:
        start = time.time()
        response = await client.get(f"{omnicorn_server}/")
        elapsed = time.time() - start
        
        assert response.status_code == 200
        # Response should be under 1 second
        assert elapsed < 1.0

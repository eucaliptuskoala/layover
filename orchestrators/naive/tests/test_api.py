"""
HTTP API tests for Naive Saga Orchestrator service endpoints.
"""

import httpx
import pytest

from main import app


@pytest.mark.asyncio
async def test_health_check_returns_ok():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.get('/health')

    assert response.status_code == 200
    assert response.json() == {'service': 'naive-orchestrator', 'status': 'ok'}


@pytest.mark.asyncio
async def test_booking_endpoint_validates_payload():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        response = await client.post('/book', json={})

    # Missing required fields should return 422 Unprocessable Entity
    assert response.status_code == 422

"""
Tests for Hotel Service Placeholder.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from main import app


@pytest.mark.asyncio
async def test_hotel_health():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url='http://test'
    ) as client:
        response = await client.get('/health')
        assert response.status_code == 200
        assert response.json() == {'service': 'hotel', 'status': 'ok'}

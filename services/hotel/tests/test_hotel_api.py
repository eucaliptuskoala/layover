"""
Integration tests for Hotel Service API endpoints.
Verifies HTTP contracts, state transitions, and compensating action idempotency.
"""

import httpx
import pytest
from database import HotelDatabase, db_instance
from main import app
from service import hotel_service_instance


@pytest.fixture(autouse=True)
async def setup_test_db(tmp_path):
    """Overrides the database with an isolated test instance for each test."""
    test_db_path = str(tmp_path / 'test_api_hotel.db')
    test_db = HotelDatabase(db_path=test_db_path)
    await test_db.init_db()

    # Wire to instances
    db_instance.db_path = test_db_path
    hotel_service_instance.db = test_db
    yield test_db


@pytest.fixture
async def client():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url='http://test',
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_reserve_hotel_success(client):
    response = await client.post(
        '/reserve',
        json={
            'booking_id': 'bk-h-1',
            'customer_id': 'user_1',
            'hotel_name': 'Hilton Prague',
            'price': 180.0,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data['booking_id'] == 'bk-h-1'
    assert data['status'] == 'RESERVED'
    assert data['price'] == 180.0


@pytest.mark.asyncio
async def test_reserve_hotel_idempotent(client):
    payload = {
        'booking_id': 'bk-h-idemp',
        'customer_id': 'user_1',
        'hotel_name': 'Hilton Prague',
        'price': 180.0,
    }
    r1 = await client.post('/reserve', json=payload)
    assert r1.status_code == 201

    r2 = await client.post('/reserve', json=payload)
    assert r2.status_code == 201
    assert r2.json()['booking_id'] == 'bk-h-idemp'


@pytest.mark.asyncio
async def test_cancel_hotel_compensation_and_idempotency(client):
    await client.post(
        '/reserve',
        json={
            'booking_id': 'bk-h-cancel',
            'customer_id': 'user_1',
            'hotel_name': 'Hilton Prague',
            'price': 180.0,
        },
    )

    r1 = await client.post('/cancel', json={'booking_id': 'bk-h-cancel'})
    assert r1.status_code == 200
    assert r1.json()['status'] == 'CANCELLED'

    # Duplicate cancellation
    r2 = await client.post('/cancel', json={'booking_id': 'bk-h-cancel'})
    assert r2.status_code == 200
    assert r2.json()['status'] == 'CANCELLED'


@pytest.mark.asyncio
async def test_cannot_confirm_cancelled_hotel(client):
    await client.post(
        '/reserve',
        json={
            'booking_id': 'bk-h-conflict',
            'customer_id': 'user_1',
            'hotel_name': 'Hilton Prague',
            'price': 180.0,
        },
    )
    await client.post('/cancel', json={'booking_id': 'bk-h-conflict'})

    response = await client.post('/confirm', json={'booking_id': 'bk-h-conflict'})
    assert response.status_code == 409
    assert 'Cannot confirm cancelled' in response.json()['detail']


@pytest.mark.asyncio
async def test_confirm_hotel_success(client):
    await client.post(
        '/reserve',
        json={
            'booking_id': 'bk-h-confirm',
            'customer_id': 'user_1',
            'hotel_name': 'Hilton Prague',
            'price': 180.0,
        },
    )

    response = await client.post('/confirm', json={'booking_id': 'bk-h-confirm'})
    assert response.status_code == 200
    assert response.json()['status'] == 'CONFIRMED'

    # Cannot cancel confirmed
    cancel_resp = await client.post('/cancel', json={'booking_id': 'bk-h-confirm'})
    assert cancel_resp.status_code == 409


@pytest.mark.asyncio
async def test_get_nonexistent_hotel_reservation(client):
    response = await client.get('/reservations/bk-ghost')
    assert response.status_code == 404

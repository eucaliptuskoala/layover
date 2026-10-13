"""
Integration tests for Flight Service API endpoints.
Verifies HTTP contracts, state transitions, and compensating action idempotency.
"""

import httpx
import pytest
from database import FlightDatabase, db_instance
from main import app
from service import flight_service_instance


@pytest.fixture(autouse=True)
async def setup_test_db(tmp_path):
    """Overrides the database with an isolated test instance for each test."""
    test_db_path = str(tmp_path / 'test_api_flight.db')
    test_db = FlightDatabase(db_path=test_db_path)
    await test_db.init_db()

    # Wire to instances
    db_instance.db_path = test_db_path
    flight_service_instance.db = test_db
    yield test_db


@pytest.fixture
async def client():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url='http://test',
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_reserve_flight_success(client):
    response = await client.post(
        '/reserve',
        json={
            'booking_id': 'bk-f-1',
            'customer_id': 'user_1',
            'flight_number': 'FL-101',
            'price': 250.0,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data['booking_id'] == 'bk-f-1'
    assert data['status'] == 'RESERVED'
    assert data['price'] == 250.0


@pytest.mark.asyncio
async def test_reserve_flight_idempotent(client):
    payload = {
        'booking_id': 'bk-f-idemp',
        'customer_id': 'user_1',
        'flight_number': 'FL-101',
        'price': 250.0,
    }
    r1 = await client.post('/reserve', json=payload)
    assert r1.status_code == 201

    r2 = await client.post('/reserve', json=payload)
    assert r2.status_code == 201
    assert r2.json()['booking_id'] == 'bk-f-idemp'


@pytest.mark.asyncio
async def test_cancel_flight_compensation_and_idempotency(client):
    # 1. Reserve
    await client.post(
        '/reserve',
        json={
            'booking_id': 'bk-f-cancel',
            'customer_id': 'user_1',
            'flight_number': 'FL-101',
            'price': 250.0,
        },
    )

    # 2. First cancellation (compensating action)
    r1 = await client.post('/cancel', json={'booking_id': 'bk-f-cancel'})
    assert r1.status_code == 200
    assert r1.json()['status'] == 'CANCELLED'

    # 3. Duplicate cancellation (network retry in Saga)
    r2 = await client.post('/cancel', json={'booking_id': 'bk-f-cancel'})
    assert r2.status_code == 200
    assert r2.json()['status'] == 'CANCELLED'


@pytest.mark.asyncio
async def test_cannot_confirm_cancelled_flight(client):
    await client.post(
        '/reserve',
        json={
            'booking_id': 'bk-f-conflict',
            'customer_id': 'user_1',
            'flight_number': 'FL-101',
            'price': 250.0,
        },
    )
    await client.post('/cancel', json={'booking_id': 'bk-f-conflict'})

    # Attempt confirm after cancel
    response = await client.post('/confirm', json={'booking_id': 'bk-f-conflict'})
    assert response.status_code == 409
    assert 'Cannot confirm cancelled' in response.json()['detail']


@pytest.mark.asyncio
async def test_confirm_flight_success(client):
    await client.post(
        '/reserve',
        json={
            'booking_id': 'bk-f-confirm',
            'customer_id': 'user_1',
            'flight_number': 'FL-101',
            'price': 250.0,
        },
    )

    response = await client.post('/confirm', json={'booking_id': 'bk-f-confirm'})
    assert response.status_code == 200
    assert response.json()['status'] == 'CONFIRMED'

    # Cannot cancel confirmed
    cancel_resp = await client.post('/cancel', json={'booking_id': 'bk-f-confirm'})
    assert cancel_resp.status_code == 409


@pytest.mark.asyncio
async def test_get_nonexistent_reservation(client):
    response = await client.get('/reservations/bk-ghost')
    assert response.status_code == 404

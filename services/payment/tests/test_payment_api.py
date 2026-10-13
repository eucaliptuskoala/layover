"""
Integration tests for Payment Service API endpoints.
Verifies HTTP contracts, balance verification, charges, and compensating refund idempotency.
"""

import httpx
import pytest
from database import PaymentDatabase, db_instance
from main import app
from service import payment_service_instance


@pytest.fixture(autouse=True)
async def setup_test_db(tmp_path):
    """Overrides the database with an isolated test instance for each test."""
    test_db_path = str(tmp_path / 'test_api_payment.db')
    test_db = PaymentDatabase(db_path=test_db_path)
    await test_db.init_db()

    # Wire to instances
    db_instance.db_path = test_db_path
    payment_service_instance.db = test_db
    yield test_db


@pytest.fixture
async def client():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url='http://test',
    ) as ac:
        yield ac


@pytest.mark.asyncio
async def test_get_initial_balance(client):
    response = await client.get('/account/user_1')
    assert response.status_code == 200
    assert response.json()['customer_id'] == 'user_1'
    assert response.json()['balance'] == 1000.0


@pytest.mark.asyncio
async def test_charge_success_and_balance_deduction(client):
    response = await client.post(
        '/charge',
        json={
            'booking_id': 'bk-p-1',
            'customer_id': 'user_1',
            'amount': 300.0,
        },
    )
    assert response.status_code == 201
    assert response.json()['status'] == 'CHARGED'
    assert response.json()['amount'] == 300.0

    # Verify balance
    acct = await client.get('/account/user_1')
    assert acct.json()['balance'] == 700.0


@pytest.mark.asyncio
async def test_charge_idempotent_no_double_deduction(client):
    payload = {
        'booking_id': 'bk-p-idemp',
        'customer_id': 'user_1',
        'amount': 250.0,
    }
    r1 = await client.post('/charge', json=payload)
    assert r1.status_code == 201

    r2 = await client.post('/charge', json=payload)
    assert r2.status_code == 201

    # Verify balance was only deducted ONCE (1000 - 250 = 750)
    acct = await client.get('/account/user_1')
    assert acct.json()['balance'] == 750.0


@pytest.mark.asyncio
async def test_insufficient_funds_rejected(client):
    response = await client.post(
        '/charge',
        json={
            'booking_id': 'bk-p-broke',
            'customer_id': 'user_1',
            'amount': 1500.0,
        },
    )
    assert response.status_code == 400
    assert 'Insufficient funds' in response.json()['detail']

    # Balance remains 1000.0
    acct = await client.get('/account/user_1')
    assert acct.json()['balance'] == 1000.0


@pytest.mark.asyncio
async def test_refund_success_and_idempotency(client):
    # 1. Charge 400.0
    await client.post(
        '/charge',
        json={
            'booking_id': 'bk-p-refund',
            'customer_id': 'user_1',
            'amount': 400.0,
        },
    )
    acct = await client.get('/account/user_1')
    assert acct.json()['balance'] == 600.0

    # 2. First refund (compensating action)
    r1 = await client.post('/refund', json={'booking_id': 'bk-p-refund'})
    assert r1.status_code == 200
    assert r1.json()['status'] == 'REFUNDED'

    acct_after = await client.get('/account/user_1')
    assert acct_after.json()['balance'] == 1000.0

    # 3. Duplicate refund (network retry in Saga)
    r2 = await client.post('/refund', json={'booking_id': 'bk-p-refund'})
    assert r2.status_code == 200
    assert r2.json()['status'] == 'REFUNDED'

    # Balance must NOT be refunded twice
    acct_final = await client.get('/account/user_1')
    assert acct_final.json()['balance'] == 1000.0


@pytest.mark.asyncio
async def test_get_nonexistent_payment(client):
    response = await client.get('/payment/bk-ghost')
    assert response.status_code == 404

"""
Unit tests for PaymentDatabase operations.
Verifies accounts, atomic charges, insufficient funds errors, and balance refunds.
"""

import pytest
from database import PaymentDatabase
from models import PaymentStatus


@pytest.fixture
async def payment_db(tmp_path):
    """Provides a fresh isolated PaymentDatabase in a temporary path."""
    test_db_path = str(tmp_path / 'test_payment.db')
    db = PaymentDatabase(db_path=test_db_path)
    await db.init_db()
    return db


@pytest.mark.asyncio
async def test_initial_account_seed(payment_db):
    account = await payment_db.get_account('user_1')
    assert account is not None
    assert account['customer_id'] == 'user_1'
    assert account['balance'] == 1000.0


@pytest.mark.asyncio
async def test_successful_charge(payment_db):
    payment = await payment_db.charge(
        booking_id='bk-pay-1',
        customer_id='user_1',
        amount=350.0,
    )

    assert payment['booking_id'] == 'bk-pay-1'
    assert payment['customer_id'] == 'user_1'
    assert payment['amount'] == 350.0
    assert payment['status'] == PaymentStatus.CHARGED.value

    # Check updated balance: 1000 - 350 = 650
    account = await payment_db.get_account('user_1')
    assert account['balance'] == 650.0


@pytest.mark.asyncio
async def test_insufficient_funds(payment_db):
    with pytest.raises(ValueError, match='Insufficient funds'):
        await payment_db.charge(
            booking_id='bk-pay-over',
            customer_id='user_1',
            amount=1500.0,
        )

    # Balance remains intact
    account = await payment_db.get_account('user_1')
    assert account['balance'] == 1000.0


@pytest.mark.asyncio
async def test_successful_refund(payment_db):
    # Charge 400.0
    await payment_db.charge(
        booking_id='bk-pay-2',
        customer_id='user_1',
        amount=400.0,
    )
    account_after_charge = await payment_db.get_account('user_1')
    assert account_after_charge['balance'] == 600.0

    # Compensating action: refund
    refunded_payment = await payment_db.refund('bk-pay-2')
    assert refunded_payment['status'] == PaymentStatus.REFUNDED.value

    # Balance restored back to 1000.0
    account_after_refund = await payment_db.get_account('user_1')
    assert account_after_refund['balance'] == 1000.0


@pytest.mark.asyncio
async def test_double_refund_fails(payment_db):
    await payment_db.charge(
        booking_id='bk-pay-3',
        customer_id='user_1',
        amount=200.0,
    )
    await payment_db.refund('bk-pay-3')

    with pytest.raises(ValueError, match='already been refunded'):
        await payment_db.refund('bk-pay-3')

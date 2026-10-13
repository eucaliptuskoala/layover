"""
Unit tests for FlightDatabase operations.
Verifies table creation, reservation persistence, and state transitions.
"""

import pytest
from database import FlightDatabase
from models import FlightBookingStatus


@pytest.fixture
async def flight_db(tmp_path):
    """Provides a fresh isolated FlightDatabase in a temporary path."""
    test_db_path = str(tmp_path / 'test_flight.db')
    db = FlightDatabase(db_path=test_db_path)
    await db.init_db()
    return db


@pytest.mark.asyncio
async def test_create_and_get_flight_reservation(flight_db):
    reservation = await flight_db.create_reservation(
        booking_id='bk-100',
        customer_id='user_1',
        flight_number='FL-101',
        price=250.0,
    )

    assert reservation['booking_id'] == 'bk-100'
    assert reservation['flight_number'] == 'FL-101'
    assert reservation['price'] == 250.0
    assert reservation['status'] == FlightBookingStatus.RESERVED.value

    fetched = await flight_db.get_reservation('bk-100')
    assert fetched is not None
    assert fetched['id'] == reservation['id']
    assert fetched['booking_id'] == 'bk-100'


@pytest.mark.asyncio
async def test_update_status_transitions(flight_db):
    await flight_db.create_reservation(
        booking_id='bk-200',
        customer_id='user_1',
        flight_number='FL-202',
        price=320.0,
    )

    # Transition to CONFIRMED
    confirmed = await flight_db.update_status('bk-200', FlightBookingStatus.CONFIRMED)
    assert confirmed['status'] == FlightBookingStatus.CONFIRMED.value

    # Transition to CANCELLED (Compensating action)
    cancelled = await flight_db.update_status('bk-200', FlightBookingStatus.CANCELLED)
    assert cancelled['status'] == FlightBookingStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_list_reservations(flight_db):
    await flight_db.create_reservation(
        booking_id='bk-301',
        customer_id='user_1',
        flight_number='FL-301',
        price=100.0,
    )
    await flight_db.create_reservation(
        booking_id='bk-302',
        customer_id='user_2',
        flight_number='FL-302',
        price=150.0,
    )

    all_reservations = await flight_db.list_reservations()
    assert len(all_reservations) == 2

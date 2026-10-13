"""
Unit tests for HotelDatabase operations.
Verifies table creation, reservation persistence, and state transitions.
"""

import pytest
from database import HotelDatabase
from models import HotelBookingStatus


@pytest.fixture
async def hotel_db(tmp_path):
    """Provides a fresh isolated HotelDatabase in a temporary path."""
    test_db_path = str(tmp_path / 'test_hotel.db')
    db = HotelDatabase(db_path=test_db_path)
    await db.init_db()
    return db


@pytest.mark.asyncio
async def test_create_and_get_hotel_reservation(hotel_db):
    reservation = await hotel_db.create_reservation(
        booking_id='bk-101',
        customer_id='user_1',
        hotel_name='Hilton Prague',
        price=180.0,
    )

    assert reservation['booking_id'] == 'bk-101'
    assert reservation['hotel_name'] == 'Hilton Prague'
    assert reservation['price'] == 180.0
    assert reservation['status'] == HotelBookingStatus.RESERVED.value

    fetched = await hotel_db.get_reservation('bk-101')
    assert fetched is not None
    assert fetched['id'] == reservation['id']
    assert fetched['booking_id'] == 'bk-101'


@pytest.mark.asyncio
async def test_update_hotel_status_transitions(hotel_db):
    await hotel_db.create_reservation(
        booking_id='bk-202',
        customer_id='user_1',
        hotel_name='Marriott Berlin',
        price=210.0,
    )

    # Transition to CONFIRMED
    confirmed = await hotel_db.update_status('bk-202', HotelBookingStatus.CONFIRMED)
    assert confirmed['status'] == HotelBookingStatus.CONFIRMED.value

    # Transition to CANCELLED (Compensating action)
    cancelled = await hotel_db.update_status('bk-202', HotelBookingStatus.CANCELLED)
    assert cancelled['status'] == HotelBookingStatus.CANCELLED.value


@pytest.mark.asyncio
async def test_list_hotel_reservations(hotel_db):
    await hotel_db.create_reservation(
        booking_id='bk-303',
        customer_id='user_1',
        hotel_name='Ibis Vienna',
        price=90.0,
    )
    await hotel_db.create_reservation(
        booking_id='bk-304',
        customer_id='user_2',
        hotel_name='Hyatt Zurich',
        price=350.0,
    )

    all_reservations = await hotel_db.list_reservations()
    assert len(all_reservations) == 2

"""
Scenario profiles and procedural test data generator for travel bookings.
Supports standard Happy Path and deterministic failure scenarios for Saga testing.
"""

import uuid
from typing import Dict
from models import BookingRequest, ScenarioType


def generate_booking_id() -> str:
    """Generates a random unique booking ID."""
    return f'bk-{uuid.uuid4().hex[:8]}'


DEFAULT_SCENARIOS: Dict[ScenarioType, Dict] = {
    ScenarioType.HAPPY_PATH: {
        'customer_id': 'user_1',
        'flight_number': 'LH-204',
        'flight_price': 250.0,
        'hotel_name': 'Grand Palace Hotel',
        'hotel_price': 150.0,
        'description': 'Valid reservation within user balance ($400 total <= $1000 balance). Expects CONFIRMED.',
    },
    ScenarioType.FAIL_PAYMENT: {
        'customer_id': 'user_1',
        'flight_number': 'KLM-401',
        'flight_price': 1200.0,
        'hotel_name': 'Luxury Resort & Spa',
        'hotel_price': 1300.0,
        'description': 'Exceeds account balance ($2500 total > $1000 balance). Payment rejects (400), triggers LIFO rollback.',
    },
    ScenarioType.FAIL_HOTEL: {
        'customer_id': 'user_1',
        'flight_number': 'AF-310',
        'flight_price': 300.0,
        'hotel_name': 'INVALID_HOTEL_OVERBOOKED',
        'hotel_price': -1.0,  # Negative price triggers 422 Unprocessable Entity rejection at Hotel API
        'description': 'Hotel reservation rejected (422 Unprocessable). Triggers immediate flight cancellation.',
    },
}


def resolve_booking_payload(request: BookingRequest) -> Dict:
    """
    Merges request parameters with predefined scenario defaults and procedural IDs.
    Returns a complete normalized payload dictionary.
    """
    scenario_defaults = DEFAULT_SCENARIOS.get(
        request.scenario,
        DEFAULT_SCENARIOS[ScenarioType.HAPPY_PATH],
    )

    booking_id = request.booking_id or generate_booking_id()
    customer_id = request.customer_id or scenario_defaults['customer_id']
    flight_number = request.flight_number or scenario_defaults['flight_number']
    flight_price = request.flight_price if request.flight_price is not None else scenario_defaults['flight_price']
    hotel_name = request.hotel_name or scenario_defaults['hotel_name']
    hotel_price = request.hotel_price if request.hotel_price is not None else scenario_defaults['hotel_price']

    return {
        'booking_id': booking_id,
        'customer_id': customer_id,
        'flight_number': flight_number,
        'flight_price': float(flight_price),
        'hotel_name': hotel_name,
        'hotel_price': float(hotel_price),
        'total_amount': round(float(flight_price) + float(hotel_price), 2),
    }

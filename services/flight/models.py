"""
Flight Service Schemas and Data Models.
Defines Pydantic models for reservations, confirmations, and cancellations.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class FlightBookingStatus(str, Enum):
    RESERVED = 'RESERVED'
    CONFIRMED = 'CONFIRMED'
    CANCELLED = 'CANCELLED'


class FlightReservationRequest(BaseModel):
    booking_id: str = Field(..., description='Unique global transaction / booking ID')
    customer_id: str = Field(..., description='Customer account identifier')
    flight_number: str = Field(..., description='Flight code (e.g. FL-101)')
    price: float = Field(..., gt=0, description='Price for the flight reservation')


class FlightReservationResponse(BaseModel):
    id: int
    booking_id: str
    customer_id: str
    flight_number: str
    price: float
    status: FlightBookingStatus
    created_at: str


class FlightCancellationRequest(BaseModel):
    booking_id: str
    reason: Optional[str] = None


class FlightConfirmationRequest(BaseModel):
    booking_id: str

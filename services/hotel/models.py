"""
Hotel Service Schemas and Data Models.
Defines Pydantic models for reservations, confirmations, and cancellations.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class HotelBookingStatus(str, Enum):
    RESERVED = 'RESERVED'
    CONFIRMED = 'CONFIRMED'
    CANCELLED = 'CANCELLED'


class HotelReservationRequest(BaseModel):
    booking_id: str = Field(..., description='Unique global transaction / booking ID')
    customer_id: str = Field(..., description='Customer account identifier')
    hotel_name: str = Field(..., description='Name of hotel (e.g. Hilton Prague)')
    price: float = Field(..., gt=0, description='Price for the hotel reservation')


class HotelReservationResponse(BaseModel):
    id: int
    booking_id: str
    customer_id: str
    hotel_name: str
    price: float
    status: HotelBookingStatus
    created_at: str


class HotelCancellationRequest(BaseModel):
    booking_id: str
    reason: Optional[str] = None


class HotelConfirmationRequest(BaseModel):
    booking_id: str

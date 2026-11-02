"""
Data contracts and DTO schemas for Temporal Saga activities and workflow.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class BookingWorkflowInput(BaseModel):
    """Input payload to start a travel booking workflow."""

    booking_id: str = Field(description='Global correlation ID for the booking')
    customer_id: str = Field(description='Customer identifier')
    flight_number: str = Field(description='Flight identifier')
    flight_price: float = Field(description='Price for flight reservation')
    hotel_name: str = Field(description='Hotel name')
    hotel_price: float = Field(description='Price for hotel room reservation')

    @property
    def total_amount(self) -> float:
        return round(self.flight_price + self.hotel_price, 2)


class FlightReservationRequest(BaseModel):
    booking_id: str
    customer_id: str
    flight_number: str
    price: float


class FlightCancellationRequest(BaseModel):
    booking_id: str
    reason: str = 'Booking cancelled due to subsequent workflow failure'


class FlightConfirmationRequest(BaseModel):
    booking_id: str


class FlightResponse(BaseModel):
    booking_id: str
    customer_id: str
    flight_number: str
    price: float
    status: str


class HotelReservationRequest(BaseModel):
    booking_id: str
    customer_id: str
    hotel_name: str
    price: float


class HotelCancellationRequest(BaseModel):
    booking_id: str
    reason: str = 'Booking cancelled due to subsequent workflow failure'


class HotelConfirmationRequest(BaseModel):
    booking_id: str


class HotelResponse(BaseModel):
    booking_id: str
    customer_id: str
    hotel_name: str
    price: float
    status: str


class PaymentChargeRequest(BaseModel):
    booking_id: str
    customer_id: str
    amount: float


class PaymentRefundRequest(BaseModel):
    booking_id: str
    reason: str = 'Booking cancelled due to subsequent workflow failure'


class PaymentResponse(BaseModel):
    payment_id: str
    booking_id: str
    customer_id: str
    amount: float
    status: str


class BookingWorkflowResult(BaseModel):
    """Outcome of the BookingWorkflow Saga execution."""

    booking_id: str
    customer_id: str
    status: str  # 'CONFIRMED', 'COMPENSATED', 'FAILED'
    total_amount: float
    steps_completed: List[str] = Field(default_factory=list)
    compensations_executed: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None

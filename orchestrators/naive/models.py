"""Coordinator-owned contracts; intentionally independent of the gateway and Temporal."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class NaiveSagaInput(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)

    booking_id: str = Field(min_length=1)
    customer_id: str
    flight_number: str
    flight_price: float
    hotel_name: str
    hotel_price: float

    @property
    def total_amount(self) -> float:
        # Do not reject negative fault-fixture prices before the owning service sees them.
        return round(self.flight_price + self.hotel_price, 2)


class NaiveSagaResult(BaseModel):
    booking_id: str
    status: Literal['CONFIRMED', 'COMPENSATED', 'FAILED']
    total_amount: float
    steps_completed: list[str] = Field(default_factory=list)
    compensations_executed: list[str] = Field(default_factory=list)
    error_message: str | None = None


class ServiceAcknowledgment(BaseModel):
    """Only fields needed to acknowledge an action, not a copy of service-owned records."""

    booking_id: str
    status: str

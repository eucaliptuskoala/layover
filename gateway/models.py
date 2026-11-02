"""
Unified data contracts and schemas for the Gateway layer.
Shared between CLI client and future Web UI dashboard.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


class OrchestratorType(str, Enum):
    """Orchestrator engine choices for booking execution."""

    TEMPORAL = 'temporal'
    NAIVE = 'naive'  # In-memory Saga baseline with ad-hoc LIFO rollbacks


class ScenarioType(str, Enum):
    HAPPY_PATH = 'happy_path'
    FAIL_HOTEL = 'fail_hotel'
    FAIL_PAYMENT = 'fail_payment'
    CUSTOM = 'custom'


class BookingRequest(BaseModel):
    """Unified booking dispatch request."""

    orchestrator: OrchestratorType = Field(
        default=OrchestratorType.TEMPORAL,
        description='Orchestrator engine to execute the booking',
    )
    scenario: ScenarioType = Field(
        default=ScenarioType.HAPPY_PATH,
        description='Predefined testing scenario or custom parameters',
    )
    booking_id: Optional[str] = Field(
        default=None,
        description='Optional custom booking ID (auto-generated if omitted)',
    )
    customer_id: Optional[str] = None
    flight_number: Optional[str] = None
    flight_price: Optional[float] = None
    hotel_name: Optional[str] = None
    hotel_price: Optional[float] = None


class BookingResponse(BaseModel):
    """Unified booking dispatch response."""

    booking_id: str
    orchestrator: str
    scenario: str
    status: str  # 'CONFIRMED', 'COMPENSATED', 'FAILED'
    total_amount: float
    steps_completed: List[str] = Field(default_factory=list)
    compensations_executed: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None
    temporal_ui_url: Optional[str] = None


class ServiceHealth(BaseModel):
    name: str
    url: str
    status: str  # 'UP' or 'DOWN'
    latency_ms: Optional[float] = None
    error: Optional[str] = None


class SystemHealthReport(BaseModel):
    overall_status: str  # 'HEALTHY' or 'DEGRADED'
    services: List[ServiceHealth]

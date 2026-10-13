"""
Payment Service Schemas and Data Models.
Defines Pydantic models for customer accounts, charges, and refunds.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class PaymentStatus(str, Enum):
    CHARGED = 'CHARGED'
    REFUNDED = 'REFUNDED'
    FAILED = 'FAILED'


class AccountResponse(BaseModel):
    customer_id: str
    balance: float


class PaymentChargeRequest(BaseModel):
    booking_id: str = Field(..., description='Unique global transaction / booking ID')
    customer_id: str = Field(..., description='Customer account identifier')
    amount: float = Field(..., gt=0, description='Amount to charge')


class PaymentChargeResponse(BaseModel):
    id: int
    payment_id: str
    booking_id: str
    customer_id: str
    amount: float
    status: PaymentStatus
    created_at: str


class PaymentRefundRequest(BaseModel):
    booking_id: str
    reason: Optional[str] = None


class PaymentRefundResponse(BaseModel):
    id: int
    payment_id: str
    booking_id: str
    customer_id: str
    amount: float
    status: PaymentStatus
    created_at: str

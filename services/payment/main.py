"""
Payment Service Application.
Exposes REST API endpoints for customer charges and compensating refunds.
"""

from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, HTTPException, status
from database import db_instance
from models import (
    AccountResponse,
    PaymentChargeRequest,
    PaymentChargeResponse,
    PaymentRefundRequest,
    PaymentRefundResponse,
)
from service import (
    AccountNotFoundError,
    InsufficientFundsError,
    PaymentConflictError,
    PaymentNotFoundError,
    payment_service_instance,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes SQLite schema and demo account on application startup."""
    await db_instance.init_db()
    yield


app = FastAPI(
    title='Payment Service',
    description='Microservice managing payments, customer balances, and refunds',
    version='0.1.0',
    lifespan=lifespan,
)


@app.get('/health')
async def health_check():
    return {'service': 'payment', 'status': 'ok'}


@app.post(
    '/charge',
    response_model=PaymentChargeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def charge_payment(request: PaymentChargeRequest):
    try:
        payment = await payment_service_instance.charge(request)
        return payment
    except InsufficientFundsError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PaymentConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@app.post(
    '/refund',
    response_model=PaymentRefundResponse,
    status_code=status.HTTP_200_OK,
)
async def refund_payment(request: PaymentRefundRequest):
    try:
        payment = await payment_service_instance.refund(
            booking_id=request.booking_id,
            reason=request.reason,
        )
        return payment
    except PaymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except PaymentConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@app.get(
    '/account/{customer_id}',
    response_model=AccountResponse,
    status_code=status.HTTP_200_OK,
)
async def get_account(customer_id: str):
    try:
        return await payment_service_instance.get_account(customer_id)
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@app.get(
    '/payment/{booking_id}',
    response_model=PaymentChargeResponse,
    status_code=status.HTTP_200_OK,
)
async def get_payment(booking_id: str):
    try:
        return await payment_service_instance.get_payment(booking_id)
    except PaymentNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@app.get(
    '/payments',
    response_model=List[PaymentChargeResponse],
    status_code=status.HTTP_200_OK,
)
async def list_payments():
    return await payment_service_instance.list_payments()

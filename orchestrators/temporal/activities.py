"""
Temporal Activities executing HTTP REST calls to Flight, Hotel, and Payment microservices.
Distinguishes between retryable transient network errors and non-retryable business failures.
"""

import os
import httpx
from temporalio import activity
from temporalio.exceptions import ApplicationError

from models import (
    FlightCancellationRequest,
    FlightConfirmationRequest,
    FlightReservationRequest,
    FlightResponse,
    HotelCancellationRequest,
    HotelConfirmationRequest,
    HotelReservationRequest,
    HotelResponse,
    PaymentChargeRequest,
    PaymentRefundRequest,
    PaymentResponse,
)


def get_flight_url() -> str:
    return os.getenv('FLIGHT_SERVICE_URL', 'http://localhost:8001')


def get_hotel_url() -> str:
    return os.getenv('HOTEL_SERVICE_URL', 'http://localhost:8002')


def get_payment_url() -> str:
    return os.getenv('PAYMENT_SERVICE_URL', 'http://localhost:8003')


# ==========================================
# Flight Activities (Forward & Compensation)
# ==========================================

@activity.defn
async def reserve_flight_activity(request: FlightReservationRequest) -> FlightResponse:
    """Reserves a seat in Flight Service."""
    url = f'{get_flight_url()}/reserve'
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(url, json=request.model_dump())
        except httpx.RequestError as exc:
            raise ApplicationError(f'Flight service unreachable: {exc}', non_retryable=False)

    if response.status_code == 201:
        return FlightResponse(**response.json())

    # Business failure (e.g. 409 Conflict, 422 Unprocessable)
    raise ApplicationError(
        f'Flight reservation rejected ({response.status_code}): {response.text}',
        non_retryable=True,
    )


@activity.defn
async def cancel_flight_activity(request: FlightCancellationRequest) -> FlightResponse:
    """Compensating action: Cancels a reserved flight."""
    url = f'{get_flight_url()}/cancel'
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(url, json=request.model_dump())
        except httpx.RequestError as exc:
            raise ApplicationError(f'Flight cancel unreachable: {exc}', non_retryable=False)

    if response.status_code == 200:
        return FlightResponse(**response.json())

    raise ApplicationError(
        f'Flight cancellation failed ({response.status_code}): {response.text}',
        non_retryable=True,
    )


@activity.defn
async def confirm_flight_activity(request: FlightConfirmationRequest) -> FlightResponse:
    """Finalizes flight reservation to CONFIRMED."""
    url = f'{get_flight_url()}/confirm'
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(url, json=request.model_dump())
        except httpx.RequestError as exc:
            raise ApplicationError(f'Flight confirm unreachable: {exc}', non_retryable=False)

    if response.status_code == 200:
        return FlightResponse(**response.json())

    raise ApplicationError(
        f'Flight confirmation failed ({response.status_code}): {response.text}',
        non_retryable=True,
    )


# =========================================
# Hotel Activities (Forward & Compensation)
# =========================================

@activity.defn
async def reserve_hotel_activity(request: HotelReservationRequest) -> HotelResponse:
    """Reserves a room in Hotel Service."""
    url = f'{get_hotel_url()}/reserve'
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(url, json=request.model_dump())
        except httpx.RequestError as exc:
            raise ApplicationError(f'Hotel service unreachable: {exc}', non_retryable=False)

    if response.status_code == 201:
        return HotelResponse(**response.json())

    raise ApplicationError(
        f'Hotel reservation rejected ({response.status_code}): {response.text}',
        non_retryable=True,
    )


@activity.defn
async def cancel_hotel_activity(request: HotelCancellationRequest) -> HotelResponse:
    """Compensating action: Cancels a reserved hotel room."""
    url = f'{get_hotel_url()}/cancel'
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(url, json=request.model_dump())
        except httpx.RequestError as exc:
            raise ApplicationError(f'Hotel cancel unreachable: {exc}', non_retryable=False)

    if response.status_code == 200:
        return HotelResponse(**response.json())

    raise ApplicationError(
        f'Hotel cancellation failed ({response.status_code}): {response.text}',
        non_retryable=True,
    )


@activity.defn
async def confirm_hotel_activity(request: HotelConfirmationRequest) -> HotelResponse:
    """Finalizes hotel reservation to CONFIRMED."""
    url = f'{get_hotel_url()}/confirm'
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(url, json=request.model_dump())
        except httpx.RequestError as exc:
            raise ApplicationError(f'Hotel confirm unreachable: {exc}', non_retryable=False)

    if response.status_code == 200:
        return HotelResponse(**response.json())

    raise ApplicationError(
        f'Hotel confirmation failed ({response.status_code}): {response.text}',
        non_retryable=True,
    )


# ===========================================
# Payment Activities (Forward & Compensation)
# ===========================================

@activity.defn
async def charge_payment_activity(request: PaymentChargeRequest) -> PaymentResponse:
    """Charges customer account in Payment Service."""
    url = f'{get_payment_url()}/charge'
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(url, json=request.model_dump())
        except httpx.RequestError as exc:
            raise ApplicationError(f'Payment service unreachable: {exc}', non_retryable=False)

    if response.status_code in (200, 201):
        return PaymentResponse(**response.json())

    # E.g. 400 Insufficient Funds
    raise ApplicationError(
        f'Payment charge rejected ({response.status_code}): {response.text}',
        non_retryable=True,
    )


@activity.defn
async def refund_payment_activity(request: PaymentRefundRequest) -> PaymentResponse:
    """Compensating action: Refunds charged payment."""
    url = f'{get_payment_url()}/refund'
    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.post(url, json=request.model_dump())
        except httpx.RequestError as exc:
            raise ApplicationError(f'Payment refund unreachable: {exc}', non_retryable=False)

    if response.status_code == 200:
        return PaymentResponse(**response.json())

    raise ApplicationError(
        f'Payment refund failed ({response.status_code}): {response.text}',
        non_retryable=True,
    )

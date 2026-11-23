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


def check_service_response(response: httpx.Response, action_name: str) -> None:
    """
    Distinguishes transient server infrastructure errors from permanent business rejections.
    - 5xx errors (e.g. 500, 502, 503, 504): transient, non_retryable=False (Temporal retries).
    - 4xx errors (e.g. 400 Insufficient Funds, 409 Conflict, 422 Unprocessable): permanent, non_retryable=True.
    """
    if response.status_code >= 500:
        raise ApplicationError(
            f'{action_name} failed with server error ({response.status_code}): {response.text}',
            non_retryable=False,
        )
    raise ApplicationError(
        f'{action_name} rejected ({response.status_code}): {response.text}',
        non_retryable=True,
    )


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

    check_service_response(response, 'Flight reservation')


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

    check_service_response(response, 'Flight cancellation')


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

    check_service_response(response, 'Flight confirmation')


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

    check_service_response(response, 'Hotel reservation')


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

    check_service_response(response, 'Hotel cancellation')


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

    check_service_response(response, 'Hotel confirmation')


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

    check_service_response(response, 'Payment charge')


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

    check_service_response(response, 'Payment refund')

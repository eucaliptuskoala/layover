"""
Flight Service Application.
Exposes REST API endpoints for flight reservations and compensating cancellations.
"""

from contextlib import asynccontextmanager
from typing import List
from fastapi import FastAPI, HTTPException, status
from database import db_instance
from models import (
    FlightCancellationRequest,
    FlightConfirmationRequest,
    FlightReservationRequest,
    FlightReservationResponse,
)
from service import (
    BookingConflictError,
    BookingNotFoundError,
    flight_service_instance,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes SQLite schema on application startup."""
    await db_instance.init_db()
    yield


app = FastAPI(
    title='Flight Service',
    description='Microservice managing seat reservations and cancellations',
    version='0.1.0',
    lifespan=lifespan,
)


@app.get('/health')
async def health_check():
    return {'service': 'flight', 'status': 'ok'}


@app.post(
    '/reserve',
    response_model=FlightReservationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def reserve_flight(request: FlightReservationRequest):
    try:
        reservation = await flight_service_instance.reserve(request)
        return reservation
    except BookingConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@app.post(
    '/cancel',
    response_model=FlightReservationResponse,
    status_code=status.HTTP_200_OK,
)
async def cancel_flight(request: FlightCancellationRequest):
    try:
        reservation = await flight_service_instance.cancel(
            booking_id=request.booking_id,
            reason=request.reason,
        )
        return reservation
    except BookingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except BookingConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@app.post(
    '/confirm',
    response_model=FlightReservationResponse,
    status_code=status.HTTP_200_OK,
)
async def confirm_flight(request: FlightConfirmationRequest):
    try:
        reservation = await flight_service_instance.confirm(booking_id=request.booking_id)
        return reservation
    except BookingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    except BookingConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@app.get(
    '/reservations/{booking_id}',
    response_model=FlightReservationResponse,
    status_code=status.HTTP_200_OK,
)
async def get_reservation(booking_id: str):
    try:
        return await flight_service_instance.get_reservation(booking_id)
    except BookingNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@app.get(
    '/reservations',
    response_model=List[FlightReservationResponse],
    status_code=status.HTTP_200_OK,
)
async def list_reservations():
    return await flight_service_instance.list_reservations()

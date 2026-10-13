"""
Flight Service Business Logic Layer.
Encapsulates state transitions, validation, and idempotent saga compensation rules.
"""

from typing import Any, Dict, List, Optional
from database import FlightDatabase, db_instance
from models import FlightBookingStatus, FlightReservationRequest


class BookingNotFoundError(Exception):
    """Raised when a requested booking does not exist."""
    pass


class BookingConflictError(Exception):
    """Raised when an invalid or conflicting state transition is requested."""
    pass


class FlightService:
    """Business logic for flight reservations, confirmations, and cancellations."""

    def __init__(self, db: FlightDatabase = db_instance):
        self.db = db

    async def reserve(self, request: FlightReservationRequest) -> Dict[str, Any]:
        """Creates a new flight reservation idempotently."""
        existing = await self.db.get_reservation(request.booking_id)
        if existing:
            if existing['flight_number'] == request.flight_number and existing['status'] == FlightBookingStatus.RESERVED.value:
                return existing
            raise BookingConflictError(
                f'Booking {request.booking_id} already exists with status {existing["status"]}'
            )

        return await self.db.create_reservation(
            booking_id=request.booking_id,
            customer_id=request.customer_id,
            flight_number=request.flight_number,
            price=request.price,
            status=FlightBookingStatus.RESERVED,
        )

    async def cancel(self, booking_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """Compensating action: idempotently cancels an existing reservation."""
        existing = await self.db.get_reservation(booking_id)
        if not existing:
            raise BookingNotFoundError(f'Booking {booking_id} not found')

        # Idempotency: if already cancelled, return cleanly without failure
        if existing['status'] == FlightBookingStatus.CANCELLED.value:
            return existing

        # Reject cancellation of already confirmed bookings
        if existing['status'] == FlightBookingStatus.CONFIRMED.value:
            raise BookingConflictError(f'Cannot cancel confirmed booking {booking_id}')

        # Atomic Compare-and-Swap
        transitioned = await self.db.update_status_atomic(
            booking_id=booking_id,
            from_status=FlightBookingStatus.RESERVED,
            to_status=FlightBookingStatus.CANCELLED,
        )

        if not transitioned:
            latest = await self.db.get_reservation(booking_id)
            if latest and latest['status'] == FlightBookingStatus.CANCELLED.value:
                return latest
            raise BookingConflictError(f'Concurrent transition conflict for booking {booking_id}')

        updated = await self.db.get_reservation(booking_id)
        return updated or {}

    async def confirm(self, booking_id: str) -> Dict[str, Any]:
        """Confirms a reserved booking."""
        existing = await self.db.get_reservation(booking_id)
        if not existing:
            raise BookingNotFoundError(f'Booking {booking_id} not found')

        # Idempotency: if already confirmed, return cleanly
        if existing['status'] == FlightBookingStatus.CONFIRMED.value:
            return existing

        # Cannot confirm cancelled bookings
        if existing['status'] == FlightBookingStatus.CANCELLED.value:
            raise BookingConflictError(f'Cannot confirm cancelled booking {booking_id}')

        transitioned = await self.db.update_status_atomic(
            booking_id=booking_id,
            from_status=FlightBookingStatus.RESERVED,
            to_status=FlightBookingStatus.CONFIRMED,
        )

        if not transitioned:
            latest = await self.db.get_reservation(booking_id)
            if latest and latest['status'] == FlightBookingStatus.CONFIRMED.value:
                return latest
            raise BookingConflictError(f'Concurrent transition conflict for booking {booking_id}')

        updated = await self.db.get_reservation(booking_id)
        return updated or {}

    async def get_reservation(self, booking_id: str) -> Dict[str, Any]:
        """Retrieves a reservation or raises BookingNotFoundError."""
        existing = await self.db.get_reservation(booking_id)
        if not existing:
            raise BookingNotFoundError(f'Booking {booking_id} not found')
        return existing

    async def list_reservations(self) -> List[Dict[str, Any]]:
        """Retrieves all reservations."""
        return await self.db.list_reservations()


flight_service_instance = FlightService()

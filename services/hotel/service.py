"""
Hotel Service Business Logic Layer.
Encapsulates state transitions, validation, and idempotent saga compensation rules.
"""

from typing import Any, Dict, List, Optional
from database import HotelDatabase, db_instance
from models import HotelBookingStatus, HotelReservationRequest


class BookingNotFoundError(Exception):
    """Raised when a requested booking does not exist."""
    pass


class BookingConflictError(Exception):
    """Raised when an invalid or conflicting state transition is requested."""
    pass


class HotelService:
    """Business logic for hotel reservations, confirmations, and cancellations."""

    def __init__(self, db: HotelDatabase = db_instance):
        self.db = db

    async def reserve(self, request: HotelReservationRequest) -> Dict[str, Any]:
        """Creates a new hotel reservation idempotently."""
        existing = await self.db.get_reservation(request.booking_id)
        if existing:
            if existing['hotel_name'] == request.hotel_name and existing['status'] == HotelBookingStatus.RESERVED.value:
                return existing
            raise BookingConflictError(
                f'Booking {request.booking_id} already exists with status {existing["status"]}'
            )

        return await self.db.create_reservation(
            booking_id=request.booking_id,
            customer_id=request.customer_id,
            hotel_name=request.hotel_name,
            price=request.price,
            status=HotelBookingStatus.RESERVED,
        )

    async def cancel(self, booking_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """Compensating action: idempotently cancels an existing reservation."""
        existing = await self.db.get_reservation(booking_id)
        if not existing:
            raise BookingNotFoundError(f'Booking {booking_id} not found')

        # Idempotency: if already cancelled, return cleanly without failure
        if existing['status'] == HotelBookingStatus.CANCELLED.value:
            return existing

        # Reject cancellation of already confirmed bookings
        if existing['status'] == HotelBookingStatus.CONFIRMED.value:
            raise BookingConflictError(f'Cannot cancel confirmed booking {booking_id}')

        # Atomic Compare-and-Swap
        transitioned = await self.db.update_status_atomic(
            booking_id=booking_id,
            from_status=HotelBookingStatus.RESERVED,
            to_status=HotelBookingStatus.CANCELLED,
        )

        if not transitioned:
            latest = await self.db.get_reservation(booking_id)
            if latest and latest['status'] == HotelBookingStatus.CANCELLED.value:
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
        if existing['status'] == HotelBookingStatus.CONFIRMED.value:
            return existing

        # Cannot confirm cancelled bookings
        if existing['status'] == HotelBookingStatus.CANCELLED.value:
            raise BookingConflictError(f'Cannot confirm cancelled booking {booking_id}')

        transitioned = await self.db.update_status_atomic(
            booking_id=booking_id,
            from_status=HotelBookingStatus.RESERVED,
            to_status=HotelBookingStatus.CONFIRMED,
        )

        if not transitioned:
            latest = await self.db.get_reservation(booking_id)
            if latest and latest['status'] == HotelBookingStatus.CONFIRMED.value:
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


hotel_service_instance = HotelService()

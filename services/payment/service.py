"""
Payment Service Business Logic Layer.
Encapsulates account balance verification, charges, and idempotent saga refunds.
"""

from typing import Any, Dict, List, Optional
from database import PaymentDatabase, db_instance
from models import PaymentChargeRequest, PaymentStatus


class AccountNotFoundError(Exception):
    """Raised when the specified customer account does not exist."""
    pass


class InsufficientFundsError(Exception):
    """Raised when an account lacks sufficient balance to complete the charge."""
    pass


class PaymentNotFoundError(Exception):
    """Raised when a payment transaction is not found."""
    pass


class PaymentConflictError(Exception):
    """Raised when a payment cannot be completed due to conflicting state."""
    pass


class PaymentService:
    """Business logic for account charging, balance management, and refunds."""

    def __init__(self, db: PaymentDatabase = db_instance):
        self.db = db

    async def charge(self, request: PaymentChargeRequest) -> Dict[str, Any]:
        """Idempotently charges an account for a given booking."""
        existing = await self.db.get_payment(request.booking_id)
        if existing:
            if existing['status'] == PaymentStatus.CHARGED.value and existing['amount'] == request.amount:
                return existing
            raise PaymentConflictError(
                f'Booking {request.booking_id} already has payment status {existing["status"]}'
            )

        try:
            return await self.db.charge(
                booking_id=request.booking_id,
                customer_id=request.customer_id,
                amount=request.amount,
            )
        except ValueError as exc:
            err_msg = str(exc)
            if 'Insufficient funds' in err_msg:
                raise InsufficientFundsError(err_msg)
            if 'Account not found' in err_msg:
                raise AccountNotFoundError(err_msg)
            raise

    async def refund(self, booking_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """Compensating action: idempotently refunds a previously charged payment."""
        existing = await self.db.get_payment(booking_id)
        if not existing:
            raise PaymentNotFoundError(f'Payment for booking {booking_id} not found')

        # Idempotency: if already refunded, return cleanly without duplicating balance
        if existing['status'] == PaymentStatus.REFUNDED.value:
            return existing

        try:
            return await self.db.refund(booking_id=booking_id)
        except ValueError as exc:
            err_msg = str(exc)
            if 'already been refunded' in err_msg:
                latest = await self.db.get_payment(booking_id)
                return latest or {}
            raise

    async def get_account(self, customer_id: str) -> Dict[str, Any]:
        """Retrieves customer account and balance details."""
        account = await self.db.get_account(customer_id)
        if not account:
            raise AccountNotFoundError(f'Account {customer_id} not found')
        return account

    async def get_payment(self, booking_id: str) -> Dict[str, Any]:
        """Retrieves payment details for a booking."""
        payment = await self.db.get_payment(booking_id)
        if not payment:
            raise PaymentNotFoundError(f'Payment for booking {booking_id} not found')
        return payment

    async def list_payments(self) -> List[Dict[str, Any]]:
        """Retrieves all payment transactions."""
        return await self.db.list_payments()


payment_service_instance = PaymentService()

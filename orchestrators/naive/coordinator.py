"""Single-attempt HTTP Saga with a volatile, execution-local LIFO compensation stack."""

import logging
import os
from dataclasses import dataclass
from typing import Any

import httpx

from .models import NaiveSagaInput, NaiveSagaResult, ServiceAcknowledgment


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SagaAction:
    name: str
    url: str
    payload: dict[str, Any]
    expected_state: str


class SagaActionError(Exception):
    def __init__(self, message: str, *, outcome_unknown: bool = False):
        super().__init__(message)
        self.outcome_unknown = outcome_unknown


class NaiveSagaCoordinator:
    """No retries, persistence, restart recovery, or access to service databases.

    An injected client remains owned by its caller. Otherwise a scoped client is
    closed after each execution. Instances contain configuration, never run state.
    """

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        flight_url: str | None = None,
        hotel_url: str | None = None,
        payment_url: str | None = None,
        timeout: float = 10.0,
    ):
        self.client = client
        self.flight_url = (flight_url or os.getenv('FLIGHT_SERVICE_URL', 'http://localhost:8001')).rstrip('/')
        self.hotel_url = (hotel_url or os.getenv('HOTEL_SERVICE_URL', 'http://localhost:8002')).rstrip('/')
        self.payment_url = (payment_url or os.getenv('PAYMENT_SERVICE_URL', 'http://localhost:8003')).rstrip('/')
        self.timeout = timeout

    async def execute(self, payload: dict[str, Any]) -> NaiveSagaResult:
        input_data = NaiveSagaInput.model_validate(payload)

        if self.client is not None:
            return await self._execute(input_data, self.client)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            return await self._execute(input_data, client)

    def _actions(self, data: NaiveSagaInput) -> list[tuple[SagaAction, SagaAction | None]]:
        booking = {'booking_id': data.booking_id}
        rollback = {**booking, 'reason': f'Saga rollback for booking {data.booking_id}'}

        return [
            (
                SagaAction('reserve_flight', f'{self.flight_url}/reserve', {
                    **booking, 'customer_id': data.customer_id,
                    'flight_number': data.flight_number, 'price': data.flight_price,
                }, 'RESERVED'),
                SagaAction('cancel_flight', f'{self.flight_url}/cancel', rollback, 'CANCELLED'),
            ),
            (
                SagaAction('reserve_hotel', f'{self.hotel_url}/reserve', {
                    **booking, 'customer_id': data.customer_id,
                    'hotel_name': data.hotel_name, 'price': data.hotel_price,
                }, 'RESERVED'),
                SagaAction('cancel_hotel', f'{self.hotel_url}/cancel', rollback, 'CANCELLED'),
            ),
            (
                SagaAction('charge_payment', f'{self.payment_url}/charge', {
                    **booking, 'customer_id': data.customer_id, 'amount': data.total_amount,
                }, 'CHARGED'),
                SagaAction('refund_payment', f'{self.payment_url}/refund', rollback, 'REFUNDED'),
            ),
            (SagaAction('confirm_flight', f'{self.flight_url}/confirm', booking, 'CONFIRMED'), None),
            (SagaAction('confirm_hotel', f'{self.hotel_url}/confirm', booking, 'CONFIRMED'), None),
        ]

    async def _post(self, client: httpx.AsyncClient, action: SagaAction) -> None:
        try:
            response = await client.post(action.url, json=action.payload, timeout=self.timeout)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            # A server error or request timeout may be produced after the service committed.
            unknown = status_code >= 500 or status_code < 400 or status_code == 408
            detail = exc.response.text[:500]
            raise SagaActionError(
                f'{action.name} rejected (HTTP {status_code}): {detail}',
                outcome_unknown=unknown,
            ) from exc
        except httpx.RequestError as exc:
            raise SagaActionError(
                f'{action.name} did not return a response ({type(exc).__name__})',
                outcome_unknown=True,
            ) from exc

        try:
            acknowledgment = ServiceAcknowledgment.model_validate(response.json())
            if acknowledgment.booking_id != action.payload['booking_id']:
                raise ValueError('Response booking ID does not match the request')
            if acknowledgment.status != action.expected_state:
                raise ValueError(f'Response did not acknowledge state {action.expected_state}')
        except (ValueError, TypeError) as exc:
            raise SagaActionError(
                f'{action.name} returned an unusable acknowledgment (HTTP {response.status_code})',
                outcome_unknown=True,
            ) from exc

    async def _execute(self, data: NaiveSagaInput, client: httpx.AsyncClient) -> NaiveSagaResult:
        steps_completed: list[str] = []
        compensations_executed: list[str] = []
        compensations: list[SagaAction] = []

        try:
            for action, compensation in self._actions(data):
                await self._post(client, action)
                steps_completed.append(action.name)
                if compensation is not None:
                    compensations.append(compensation)

            return NaiveSagaResult(
                booking_id=data.booking_id,
                status='CONFIRMED',
                total_amount=data.total_amount,
                steps_completed=steps_completed,
            )

        except Exception as exc:
            # SIGKILL cannot enter this handler. Task cancellation also propagates rather
            # than pretending a volatile coordinator can guarantee shutdown recovery.
            outcome_unknown = not isinstance(exc, SagaActionError) or exc.outcome_unknown
            errors = [str(exc)]
            rollback_failed = False
            logger.warning('Naive Saga failed for booking_id=%s; attempting known rollbacks', data.booking_id)

            while compensations:
                compensation = compensations.pop()
                try:
                    await self._post(client, compensation)
                    compensations_executed.append(compensation.name)
                except Exception as rollback_exc:
                    rollback_failed = True
                    outcome_unknown |= (
                        not isinstance(rollback_exc, SagaActionError) or rollback_exc.outcome_unknown
                    )
                    errors.append(f'Compensation failed: {rollback_exc}')

            if outcome_unknown:
                errors.append('At least one action has an unknown outcome; manual reconciliation may be required.')
            elif rollback_failed:
                errors.append('Rollback is incomplete; manual reconciliation is required.')

            return NaiveSagaResult(
                booking_id=data.booking_id,
                status='COMPENSATED' if steps_completed and not rollback_failed and not outcome_unknown else 'FAILED',
                total_amount=data.total_amount,
                steps_completed=steps_completed,
                compensations_executed=compensations_executed,
                error_message=' '.join(errors),
            )

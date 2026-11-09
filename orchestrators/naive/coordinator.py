"""
Naive In-Memory Saga Coordinator.

Executes a single-attempt sequential HTTP Saga with an in-memory LIFO compensation stack.
Has zero disk persistence, no restart recovery, and no direct database access.
"""

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import httpx

try:
    from .models import NaiveSagaInput, NaiveSagaResult, ServiceAcknowledgment
except ImportError:
    from models import NaiveSagaInput, NaiveSagaResult, ServiceAcknowledgment


logger = logging.getLogger(__name__)


class SagaActionError(Exception):
    """Raised when an action fails, tracking whether the remote state is unknown."""

    def __init__(self, message: str, *, outcome_unknown: bool = False) -> None:
        super().__init__(message)
        self.outcome_unknown = outcome_unknown


class NaiveSagaCoordinator:
    """
    In-memory Saga coordinator with ad-hoc LIFO rollbacks.

    Operates purely in RAM: if this process is terminated (SIGKILL / OOM),
    the compensation stack is lost forever, demonstrating orphaned holds in databases.
    """

    def __init__(
        self,
        *,
        client: Optional[httpx.AsyncClient] = None,
        flight_url: Optional[str] = None,
        hotel_url: Optional[str] = None,
        payment_url: Optional[str] = None,
        timeout: float = 10.0,
    ) -> None:
        self.client = client
        self.flight_url = (flight_url or os.getenv('FLIGHT_SERVICE_URL', 'http://localhost:8001')).rstrip('/')
        self.hotel_url = (hotel_url or os.getenv('HOTEL_SERVICE_URL', 'http://localhost:8002')).rstrip('/')
        self.payment_url = (payment_url or os.getenv('PAYMENT_SERVICE_URL', 'http://localhost:8003')).rstrip('/')
        self.timeout = timeout

    async def execute(self, payload: Dict[str, Any]) -> NaiveSagaResult:
        """Entrypoint for executing a booking saga."""
        input_data = NaiveSagaInput.model_validate(payload)

        if self.client is not None:
            return await self._run_saga(input_data, self.client)

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            return await self._run_saga(input_data, client)

    async def _post_step(
        self,
        client: httpx.AsyncClient,
        name: str,
        url: str,
        payload: Dict[str, Any],
        expected_state: str,
    ) -> None:
        """Executes a single HTTP request and validates the service acknowledgment."""
        try:
            response = await client.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()

        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code
            is_unknown = status_code >= 500 or status_code < 400 or status_code == 408
            detail = exc.response.text[:500]
            raise SagaActionError(
                f'{name} rejected (HTTP {status_code}): {detail}',
                outcome_unknown=is_unknown,
            ) from exc

        except httpx.RequestError as exc:
            raise SagaActionError(
                f'{name} did not return a response ({type(exc).__name__})',
                outcome_unknown=True,
            ) from exc

        try:
            ack = ServiceAcknowledgment.model_validate(response.json())
            if ack.booking_id != payload['booking_id']:
                raise ValueError('Response booking ID does not match the request')
            if ack.status != expected_state:
                raise ValueError(f'Response did not acknowledge state {expected_state}')

        except (ValueError, TypeError) as exc:
            raise SagaActionError(
                f'{name} returned an unusable acknowledgment (HTTP {response.status_code})',
                outcome_unknown=True,
            ) from exc

    async def _run_saga(
        self,
        data: NaiveSagaInput,
        client: httpx.AsyncClient,
    ) -> NaiveSagaResult:
        """Coordinates the multi-step saga execution and LIFO rollbacks in memory."""
        steps_completed: List[str] = []
        compensations_executed: List[str] = []
        compensations: List[Tuple[str, str, Dict[str, Any], str]] = []

        booking = {'booking_id': data.booking_id}
        rollback = {**booking, 'reason': f'Saga rollback for booking {data.booking_id}'}

        # Sequential pipeline definitions: (step_name, url, payload, expected_state, compensation_tuple)
        pipeline = [
            (
                'reserve_flight',
                f'{self.flight_url}/reserve',
                {
                    **booking,
                    'customer_id': data.customer_id,
                    'flight_number': data.flight_number,
                    'price': data.flight_price,
                },
                'RESERVED',
                ('cancel_flight', f'{self.flight_url}/cancel', rollback, 'CANCELLED'),
            ),
            (
                'reserve_hotel',
                f'{self.hotel_url}/reserve',
                {
                    **booking,
                    'customer_id': data.customer_id,
                    'hotel_name': data.hotel_name,
                    'price': data.hotel_price,
                },
                'RESERVED',
                ('cancel_hotel', f'{self.hotel_url}/cancel', rollback, 'CANCELLED'),
            ),
            (
                'charge_payment',
                f'{self.payment_url}/charge',
                {
                    **booking,
                    'customer_id': data.customer_id,
                    'amount': data.total_amount,
                },
                'CHARGED',
                ('refund_payment', f'{self.payment_url}/refund', rollback, 'REFUNDED'),
            ),
            (
                'confirm_flight',
                f'{self.flight_url}/confirm',
                booking,
                'CONFIRMED',
                None,
            ),
            (
                'confirm_hotel',
                f'{self.hotel_url}/confirm',
                booking,
                'CONFIRMED',
                None,
            ),
        ]

        try:
            for step_name, url, step_payload, expected_state, comp in pipeline:
                # Artificial delay for manual chaos testing (e.g. docker stop / kill during live demo)
                if data.delay_seconds > 0:
                    await asyncio.sleep(data.delay_seconds)

                await self._post_step(client, step_name, url, step_payload, expected_state)
                steps_completed.append(step_name)

                if comp is not None:
                    compensations.append(comp)

            return NaiveSagaResult(
                booking_id=data.booking_id,
                status='CONFIRMED',
                total_amount=data.total_amount,
                steps_completed=steps_completed,
            )

        except Exception as exc:
            outcome_unknown = not isinstance(exc, SagaActionError) or exc.outcome_unknown
            errors = [str(exc)]
            rollback_failed = False

            logger.warning(
                f'Naive Saga failed for booking_id={data.booking_id}; executing in-memory rollbacks'
            )

            # LIFO rollback execution
            while compensations:
                comp_name, comp_url, comp_payload, comp_state = compensations.pop()
                try:
                    await self._post_step(client, comp_name, comp_url, comp_payload, comp_state)
                    compensations_executed.append(comp_name)

                except Exception as rollback_exc:
                    rollback_failed = True
                    is_unkn = not isinstance(rollback_exc, SagaActionError) or rollback_exc.outcome_unknown
                    outcome_unknown = outcome_unknown or is_unkn
                    errors.append(f'Compensation failed: {rollback_exc}')

            if outcome_unknown:
                errors.append('At least one action has an unknown outcome; manual reconciliation may be required.')
            elif rollback_failed:
                errors.append('Rollback is incomplete; manual reconciliation is required.')

            is_compensated = bool(steps_completed) and not rollback_failed and not outcome_unknown

            return NaiveSagaResult(
                booking_id=data.booking_id,
                status='COMPENSATED' if is_compensated else 'FAILED',
                total_amount=data.total_amount,
                steps_completed=steps_completed,
                compensations_executed=compensations_executed,
                error_message=' '.join(errors),
            )

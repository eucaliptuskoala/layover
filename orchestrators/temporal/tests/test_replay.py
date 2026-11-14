"""
Deterministic Replay Test Suite for Temporal BookingWorkflow.

Validates that event histories captured from real workflow executions can be
safely replayed by the Temporal Replayer, proving workflow determinism, event sourcing
integrity, and immunity to non-deterministic divergence.
"""

import pytest
import respx
from httpx import Response
from temporalio import workflow
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Replayer, Worker

from activities import (
    cancel_flight_activity,
    cancel_hotel_activity,
    charge_payment_activity,
    confirm_flight_activity,
    confirm_hotel_activity,
    refund_payment_activity,
    reserve_flight_activity,
    reserve_hotel_activity,
)
from models import BookingWorkflowInput, BookingWorkflowResult
from workflows import BookingWorkflow


ALL_ACTIVITIES = [
    reserve_flight_activity,
    cancel_flight_activity,
    confirm_flight_activity,
    reserve_hotel_activity,
    cancel_hotel_activity,
    confirm_hotel_activity,
    charge_payment_activity,
    refund_payment_activity,
]


@pytest.fixture
def replay_booking_input() -> BookingWorkflowInput:
    return BookingWorkflowInput(
        booking_id='bk-replay-test-1',
        customer_id='user_1',
        flight_number='LH-404',
        flight_price=300.0,
        hotel_name='Grand Hyatt Berlin',
        hotel_price=200.0,
    )


def mock_happy_path_services(respx_mock, booking_input: BookingWorkflowInput):
    """Mocks all downstream service endpoints to succeed."""
    respx_mock.post('http://localhost:8001/reserve').mock(
        return_value=Response(
            201,
            json={
                'id': 1,
                'booking_id': booking_input.booking_id,
                'customer_id': booking_input.customer_id,
                'flight_number': booking_input.flight_number,
                'price': booking_input.flight_price,
                'status': 'RESERVED',
                'created_at': '2026-11-14T12:00:00',
            },
        )
    )
    respx_mock.post('http://localhost:8002/reserve').mock(
        return_value=Response(
            201,
            json={
                'id': 1,
                'booking_id': booking_input.booking_id,
                'customer_id': booking_input.customer_id,
                'hotel_name': booking_input.hotel_name,
                'price': booking_input.hotel_price,
                'status': 'RESERVED',
                'created_at': '2026-11-14T12:00:00',
            },
        )
    )
    respx_mock.post('http://localhost:8003/charge').mock(
        return_value=Response(
            200,
            json={
                'payment_id': 'pay-replay-1',
                'booking_id': booking_input.booking_id,
                'customer_id': booking_input.customer_id,
                'amount': booking_input.total_amount,
                'status': 'CHARGED',
                'created_at': '2026-11-14T12:00:00',
            },
        )
    )
    respx_mock.post('http://localhost:8001/confirm').mock(
        return_value=Response(
            200,
            json={
                'id': 1,
                'booking_id': booking_input.booking_id,
                'customer_id': booking_input.customer_id,
                'flight_number': booking_input.flight_number,
                'price': booking_input.flight_price,
                'status': 'CONFIRMED',
                'created_at': '2026-11-14T12:00:00',
            },
        )
    )
    respx_mock.post('http://localhost:8002/confirm').mock(
        return_value=Response(
            200,
            json={
                'id': 1,
                'booking_id': booking_input.booking_id,
                'customer_id': booking_input.customer_id,
                'hotel_name': booking_input.hotel_name,
                'price': booking_input.hotel_price,
                'status': 'CONFIRMED',
                'created_at': '2026-11-14T12:00:00',
            },
        )
    )


def mock_payment_failure_services(respx_mock, booking_input: BookingWorkflowInput):
    """Mocks reservations to succeed, payment to decline (400), and compensations to succeed."""
    respx_mock.post('http://localhost:8001/reserve').mock(
        return_value=Response(
            201,
            json={
                'id': 1,
                'booking_id': booking_input.booking_id,
                'customer_id': booking_input.customer_id,
                'flight_number': booking_input.flight_number,
                'price': booking_input.flight_price,
                'status': 'RESERVED',
                'created_at': '2026-11-14T12:00:00',
            },
        )
    )
    respx_mock.post('http://localhost:8002/reserve').mock(
        return_value=Response(
            201,
            json={
                'id': 1,
                'booking_id': booking_input.booking_id,
                'customer_id': booking_input.customer_id,
                'hotel_name': booking_input.hotel_name,
                'price': booking_input.hotel_price,
                'status': 'RESERVED',
                'created_at': '2026-11-14T12:00:00',
            },
        )
    )
    respx_mock.post('http://localhost:8003/charge').mock(
        return_value=Response(
            400,
            json={'detail': 'Insufficient funds: balance 1000.0 < total 2500.0'},
        )
    )
    respx_mock.post('http://localhost:8002/cancel').mock(
        return_value=Response(
            200,
            json={
                'id': 1,
                'booking_id': booking_input.booking_id,
                'customer_id': booking_input.customer_id,
                'hotel_name': booking_input.hotel_name,
                'price': booking_input.hotel_price,
                'status': 'CANCELLED',
                'created_at': '2026-11-14T12:00:00',
            },
        )
    )
    respx_mock.post('http://localhost:8001/cancel').mock(
        return_value=Response(
            200,
            json={
                'id': 1,
                'booking_id': booking_input.booking_id,
                'customer_id': booking_input.customer_id,
                'flight_number': booking_input.flight_number,
                'price': booking_input.flight_price,
                'status': 'CANCELLED',
                'created_at': '2026-11-14T12:00:00',
            },
        )
    )


@pytest.mark.asyncio
async def test_replay_happy_path_history(replay_booking_input: BookingWorkflowInput):
    """
    Test 1: Replay Happy Path History
    Executes a happy path workflow, fetches the full Event History, and replays
    it via Replayer. Proves that the executed event log is 100% deterministic.
    """
    with respx.mock(assert_all_called=False) as respx_mock:
        mock_happy_path_services(respx_mock, replay_booking_input)

        async with await WorkflowEnvironment.start_time_skipping(data_converter=pydantic_data_converter) as env:
            task_queue = 'replay-happy-queue'
            workflow_id = f'wf-replay-happy-{replay_booking_input.booking_id}'

            async with Worker(
                env.client,
                task_queue=task_queue,
                workflows=[BookingWorkflow],
                activities=ALL_ACTIVITIES,
            ):
                result = await env.client.execute_workflow(
                    BookingWorkflow.run,
                    replay_booking_input,
                    id=workflow_id,
                    task_queue=task_queue,
                )
                assert result.status == 'CONFIRMED'

            # Fetch the complete immutable Event History
            handle = env.client.get_workflow_handle(workflow_id)
            history = await handle.fetch_history()
            assert len(history.events) > 0

            # Replay the historical events against the current BookingWorkflow code
            replayer = Replayer(
                workflows=[BookingWorkflow],
                data_converter=pydantic_data_converter,
            )
            replay_result = await replayer.replay_workflow(history, raise_on_replay_failure=False)

            assert replay_result.replay_failure is None


@pytest.mark.asyncio
async def test_replay_compensated_history(replay_booking_input: BookingWorkflowInput):
    """
    Test 2: Replay Compensated (Rollback) History
    Executes a rollback workflow under payment failure, fetches the Event History,
    and replays it via Replayer. Proves that LIFO compensation branches are deterministic.
    """
    with respx.mock(assert_all_called=False) as respx_mock:
        mock_payment_failure_services(respx_mock, replay_booking_input)

        async with await WorkflowEnvironment.start_time_skipping(data_converter=pydantic_data_converter) as env:
            task_queue = 'replay-rollback-queue'
            workflow_id = f'wf-replay-rollback-{replay_booking_input.booking_id}'

            async with Worker(
                env.client,
                task_queue=task_queue,
                workflows=[BookingWorkflow],
                activities=ALL_ACTIVITIES,
            ):
                result = await env.client.execute_workflow(
                    BookingWorkflow.run,
                    replay_booking_input,
                    id=workflow_id,
                    task_queue=task_queue,
                )
                assert result.status == 'COMPENSATED'
                assert result.compensations_executed == ['cancel_hotel', 'cancel_flight']

            # Fetch the complete immutable Event History
            handle = env.client.get_workflow_handle(workflow_id)
            history = await handle.fetch_history()
            assert len(history.events) > 0

            # Replay through Replayer
            replayer = Replayer(
                workflows=[BookingWorkflow],
                data_converter=pydantic_data_converter,
            )
            replay_result = await replayer.replay_workflow(history, raise_on_replay_failure=False)

            assert replay_result.replay_failure is None


@workflow.defn(name='BookingWorkflow', sandboxed=False)
class MutatedBookingWorkflow:
    """
    Deliberately non-deterministic variant of BookingWorkflow.
    Schedules an unauthorized extra activity before normal execution,
    violating the historical event sequence.
    """

    @workflow.run
    async def run(self, booking_input: BookingWorkflowInput) -> BookingWorkflowResult:
        # Deliberate sequence divergence: schedule refund before any reservation was made!
        await workflow.execute_activity(
            refund_payment_activity,
            booking_input,
            start_to_close_timeout=workflow.timedelta(seconds=5),
        )
        return BookingWorkflowResult(
            booking_id=booking_input.booking_id,
            status='CONFIRMED',
            total_amount=booking_input.total_amount,
        )


@pytest.mark.asyncio
async def test_replay_detects_non_deterministic_divergence(replay_booking_input: BookingWorkflowInput):
    """
    Test 3: Negative Test - Replay Detects Non-Determinism
    Replays a valid Happy Path history against a mutated workflow definition
    that introduces an unexpected activity call. Proves that Replayer detects
    and halts non-deterministic workflow mutations.
    """
    with respx.mock(assert_all_called=False) as respx_mock:
        mock_happy_path_services(respx_mock, replay_booking_input)

        async with await WorkflowEnvironment.start_time_skipping(data_converter=pydantic_data_converter) as env:
            task_queue = 'replay-divergence-queue'
            workflow_id = f'wf-replay-divergence-{replay_booking_input.booking_id}'

            async with Worker(
                env.client,
                task_queue=task_queue,
                workflows=[BookingWorkflow],
                activities=ALL_ACTIVITIES,
            ):
                await env.client.execute_workflow(
                    BookingWorkflow.run,
                    replay_booking_input,
                    id=workflow_id,
                    task_queue=task_queue,
                )

            handle = env.client.get_workflow_handle(workflow_id)
            history = await handle.fetch_history()

            # Attempt replay against the mutated workflow definition
            replayer = Replayer(
                workflows=[MutatedBookingWorkflow],
                data_converter=pydantic_data_converter,
            )
            replay_result = await replayer.replay_workflow(history, raise_on_replay_failure=False)

            # Replayer MUST detect the divergence and register a replay failure
            assert replay_result.replay_failure is not None

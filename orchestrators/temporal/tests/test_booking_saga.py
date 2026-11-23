"""
Integration test suite for BookingWorkflow Saga using Temporal WorkflowEnvironment and respx.
Validates Happy Path, Hotel conflict rollback, Payment insufficient funds rollback, and LIFO ordering.
"""

import pytest
import respx
from httpx import Response
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from temporalio.exceptions import ApplicationError
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
from models import BookingWorkflowInput
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
def sample_booking_input() -> BookingWorkflowInput:
    return BookingWorkflowInput(
        booking_id='bk-test-saga-1',
        customer_id='user_1',
        flight_number='LH-101',
        flight_price=350.0,
        hotel_name='Hilton Amsterdam',
        hotel_price=200.0,
    )


@pytest.mark.asyncio
async def test_booking_saga_happy_path(sample_booking_input: BookingWorkflowInput):
    """
    Scenario 1: Happy Path
    Flight, Hotel, and Payment all succeed.
    Expect status CONFIRMED and zero compensations executed.
    """
    with respx.mock(assert_all_called=False) as respx_mock:
        respx_mock.post('http://localhost:8001/reserve').mock(
            return_value=Response(
                201,
                json={
                    'id': 1,
                    'booking_id': sample_booking_input.booking_id,
                    'customer_id': sample_booking_input.customer_id,
                    'flight_number': sample_booking_input.flight_number,
                    'price': sample_booking_input.flight_price,
                    'status': 'RESERVED',
                    'created_at': '2026-10-16T12:00:00',
                },
            )
        )
        respx_mock.post('http://localhost:8002/reserve').mock(
            return_value=Response(
                201,
                json={
                    'id': 1,
                    'booking_id': sample_booking_input.booking_id,
                    'customer_id': sample_booking_input.customer_id,
                    'hotel_name': sample_booking_input.hotel_name,
                    'price': sample_booking_input.hotel_price,
                    'status': 'RESERVED',
                    'created_at': '2026-10-16T12:00:00',
                },
            )
        )
        respx_mock.post('http://localhost:8003/charge').mock(
            return_value=Response(
                200,
                json={
                    'payment_id': 'pay-1',
                    'booking_id': sample_booking_input.booking_id,
                    'customer_id': sample_booking_input.customer_id,
                    'amount': sample_booking_input.total_amount,
                    'status': 'CHARGED',
                    'created_at': '2026-10-16T12:00:00',
                },
            )
        )
        respx_mock.post('http://localhost:8001/confirm').mock(
            return_value=Response(
                200,
                json={
                    'id': 1,
                    'booking_id': sample_booking_input.booking_id,
                    'customer_id': sample_booking_input.customer_id,
                    'flight_number': sample_booking_input.flight_number,
                    'price': sample_booking_input.flight_price,
                    'status': 'CONFIRMED',
                    'created_at': '2026-10-16T12:00:00',
                },
            )
        )
        respx_mock.post('http://localhost:8002/confirm').mock(
            return_value=Response(
                200,
                json={
                    'id': 1,
                    'booking_id': sample_booking_input.booking_id,
                    'customer_id': sample_booking_input.customer_id,
                    'hotel_name': sample_booking_input.hotel_name,
                    'price': sample_booking_input.hotel_price,
                    'status': 'CONFIRMED',
                    'created_at': '2026-10-16T12:00:00',
                },
            )
        )

        async with await WorkflowEnvironment.start_time_skipping(data_converter=pydantic_data_converter) as env:
            async with Worker(
                env.client,
                task_queue='test-booking-queue',
                workflows=[BookingWorkflow],
                activities=ALL_ACTIVITIES,
            ):
                result = await env.client.execute_workflow(
                    BookingWorkflow.run,
                    sample_booking_input,
                    id='wf-test-happy-path',
                    task_queue='test-booking-queue',
                )

                assert result.status == 'CONFIRMED'
                assert result.booking_id == sample_booking_input.booking_id
                assert result.total_amount == sample_booking_input.total_amount
                assert result.steps_completed == [
                    'reserve_flight',
                    'reserve_hotel',
                    'charge_payment',
                    'confirm_flight',
                    'confirm_hotel',
                ]
                assert result.compensations_executed == []
                assert result.error_message is None


@pytest.mark.asyncio
async def test_booking_saga_hotel_failure_rollback(sample_booking_input: BookingWorkflowInput):
    """
    Scenario 2: Hotel Reservation Fails (Conflict 409)
    Flight succeeds, but Hotel rejects.
    Expect Saga to catch error, rollback Flight (/cancel), and report COMPENSATED.
    """
    with respx.mock(assert_all_called=False) as respx_mock:
        respx_mock.post('http://localhost:8001/reserve').mock(
            return_value=Response(
                201,
                json={
                    'id': 1,
                    'booking_id': sample_booking_input.booking_id,
                    'customer_id': sample_booking_input.customer_id,
                    'flight_number': sample_booking_input.flight_number,
                    'price': sample_booking_input.flight_price,
                    'status': 'RESERVED',
                },
            )
        )
        # Hotel fails with 409
        respx_mock.post('http://localhost:8002/reserve').mock(
            return_value=Response(409, text='Hotel room already booked')
        )
        # Flight cancellation must be triggered
        cancel_route = respx_mock.post('http://localhost:8001/cancel').mock(
            return_value=Response(
                200,
                json={
                    'id': 1,
                    'booking_id': sample_booking_input.booking_id,
                    'customer_id': sample_booking_input.customer_id,
                    'flight_number': sample_booking_input.flight_number,
                    'price': sample_booking_input.flight_price,
                    'status': 'CANCELLED',
                },
            )
        )

        async with await WorkflowEnvironment.start_time_skipping(data_converter=pydantic_data_converter) as env:
            async with Worker(
                env.client,
                task_queue='test-booking-queue',
                workflows=[BookingWorkflow],
                activities=ALL_ACTIVITIES,
            ):
                result = await env.client.execute_workflow(
                    BookingWorkflow.run,
                    sample_booking_input,
                    id='wf-test-hotel-fail',
                    task_queue='test-booking-queue',
                )

                assert result.status == 'COMPENSATED'
                assert result.steps_completed == ['reserve_flight']
                assert result.compensations_executed == ['cancel_flight']
                assert cancel_route.called
                assert 'Hotel reservation rejected' in result.error_message


@pytest.mark.asyncio
async def test_booking_saga_payment_failure_rollback(sample_booking_input: BookingWorkflowInput):
    """
    Scenario 3: Payment Fails (Insufficient Funds 400)
    Flight and Hotel succeed, but Payment rejects.
    Expect Saga to execute compensations in reverse order (LIFO):
    1. cancel_hotel
    2. cancel_flight
    Expect status COMPENSATED.
    """
    with respx.mock(assert_all_called=False) as respx_mock:
        respx_mock.post('http://localhost:8001/reserve').mock(
            return_value=Response(
                201,
                json={
                    'id': 1,
                    'booking_id': sample_booking_input.booking_id,
                    'customer_id': sample_booking_input.customer_id,
                    'flight_number': sample_booking_input.flight_number,
                    'price': sample_booking_input.flight_price,
                    'status': 'RESERVED',
                },
            )
        )
        respx_mock.post('http://localhost:8002/reserve').mock(
            return_value=Response(
                201,
                json={
                    'id': 1,
                    'booking_id': sample_booking_input.booking_id,
                    'customer_id': sample_booking_input.customer_id,
                    'hotel_name': sample_booking_input.hotel_name,
                    'price': sample_booking_input.hotel_price,
                    'status': 'RESERVED',
                },
            )
        )
        # Payment fails with 400 Insufficient Funds
        respx_mock.post('http://localhost:8003/charge').mock(
            return_value=Response(400, text='Insufficient funds: balance is below required amount')
        )
        # Compensations
        hotel_cancel_route = respx_mock.post('http://localhost:8002/cancel').mock(
            return_value=Response(
                200,
                json={
                    'id': 1,
                    'booking_id': sample_booking_input.booking_id,
                    'customer_id': sample_booking_input.customer_id,
                    'hotel_name': sample_booking_input.hotel_name,
                    'price': sample_booking_input.hotel_price,
                    'status': 'CANCELLED',
                },
            )
        )
        flight_cancel_route = respx_mock.post('http://localhost:8001/cancel').mock(
            return_value=Response(
                200,
                json={
                    'id': 1,
                    'booking_id': sample_booking_input.booking_id,
                    'customer_id': sample_booking_input.customer_id,
                    'flight_number': sample_booking_input.flight_number,
                    'price': sample_booking_input.flight_price,
                    'status': 'CANCELLED',
                },
            )
        )

        async with await WorkflowEnvironment.start_time_skipping(data_converter=pydantic_data_converter) as env:
            async with Worker(
                env.client,
                task_queue='test-booking-queue',
                workflows=[BookingWorkflow],
                activities=ALL_ACTIVITIES,
            ):
                result = await env.client.execute_workflow(
                    BookingWorkflow.run,
                    sample_booking_input,
                    id='wf-test-payment-fail',
                    task_queue='test-booking-queue',
                )

                assert result.status == 'COMPENSATED'
                assert result.steps_completed == ['reserve_flight', 'reserve_hotel']
                # Strict LIFO execution check: hotel must be cancelled first, then flight
                assert result.compensations_executed == ['cancel_hotel', 'cancel_flight']
                assert hotel_cancel_route.called
                assert flight_cancel_route.called
                assert 'Payment charge rejected' in result.error_message


@pytest.mark.asyncio
async def test_activity_error_classification_4xx_vs_5xx():
    """
    Verifies that HTTP 5xx responses are marked retryable (non_retryable=False),
    while HTTP 4xx responses are marked non-retryable (non_retryable=True).
    """
    from models import FlightReservationRequest

    req = FlightReservationRequest(
        booking_id='bk-retry-test',
        customer_id='user_1',
        flight_number='LH-101',
        price=350.0,
    )

    with respx.mock:
        # 500 error -> retryable
        respx.post('http://localhost:8001/reserve').mock(
            return_value=Response(500, text='Internal Server Error')
        )
        with pytest.raises(ApplicationError) as exc_info_500:
            await reserve_flight_activity(req)
        assert exc_info_500.value.non_retryable is False

    with respx.mock:
        # 422 error -> non-retryable (business rejection)
        respx.post('http://localhost:8001/reserve').mock(
            return_value=Response(422, text='Flight fully booked')
        )
        with pytest.raises(ApplicationError) as exc_info_422:
            await reserve_flight_activity(req)
        assert exc_info_422.value.non_retryable is True


@pytest.mark.asyncio
async def test_booking_saga_exhausted_compensation_failure_reports_failed(
    sample_booking_input: BookingWorkflowInput,
):
    """
    Verifies that if a compensating activity fails after exhausting all retries,
    the workflow returns status='FAILED' (instead of silently reporting COMPENSATED).
    """
    with respx.mock(assert_all_called=False) as respx_mock:
        respx_mock.post('http://localhost:8001/reserve').mock(
            return_value=Response(
                201,
                json={
                    'id': 1,
                    'booking_id': sample_booking_input.booking_id,
                    'customer_id': sample_booking_input.customer_id,
                    'flight_number': sample_booking_input.flight_number,
                    'price': sample_booking_input.flight_price,
                    'status': 'RESERVED',
                },
            )
        )
        # Hotel fails with 409
        respx_mock.post('http://localhost:8002/reserve').mock(
            return_value=Response(409, text='Hotel room already booked')
        )
        # Flight cancellation fails with non-retryable 400 error
        respx_mock.post('http://localhost:8001/cancel').mock(
            return_value=Response(400, text='Flight booking not found or already cancelled')
        )

        async with await WorkflowEnvironment.start_time_skipping(
            data_converter=pydantic_data_converter
        ) as env:
            async with Worker(
                env.client,
                task_queue='test-booking-queue',
                workflows=[BookingWorkflow],
                activities=ALL_ACTIVITIES,
            ):
                result = await env.client.execute_workflow(
                    BookingWorkflow.run,
                    sample_booking_input,
                    id='wf-test-comp-fail',
                    task_queue='test-booking-queue',
                )

                assert result.status == 'FAILED'
                assert result.steps_completed == ['reserve_flight']
                assert result.compensations_executed == []
                assert 'failed compensation(s): cancel_flight' in result.error_message


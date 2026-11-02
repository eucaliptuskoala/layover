"""
BookingWorkflow implementing the Saga Pattern with automated LIFO compensations.
"""

from datetime import timedelta
from typing import Any, List, Tuple
from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
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
    from models import (
        BookingWorkflowInput,
        BookingWorkflowResult,
        FlightCancellationRequest,
        FlightConfirmationRequest,
        FlightReservationRequest,
        HotelCancellationRequest,
        HotelConfirmationRequest,
        HotelReservationRequest,
        PaymentChargeRequest,
        PaymentRefundRequest,
    )


# Retry policy for forward activities (transient network issues)
FORWARD_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=1.5,
    maximum_attempts=3,
    maximum_interval=timedelta(seconds=5),
)

# Retry policy for compensating activities (must strongly attempt to succeed)
COMPENSATION_RETRY_POLICY = RetryPolicy(
    initial_interval=timedelta(seconds=1),
    backoff_coefficient=1.5,
    maximum_attempts=5,
    maximum_interval=timedelta(seconds=10),
)


@workflow.defn
class BookingWorkflow:
    """
    Coordinates distributed booking across Flight, Hotel, and Payment microservices.
    Implements the Saga Pattern: if any step fails, all preceding reservations are
    compensated in reverse (LIFO) order.
    """

    def __init__(self) -> None:
        self.steps_completed: List[str] = []
        self.compensations_executed: List[str] = []

    @workflow.run
    async def run(self, input_data: BookingWorkflowInput) -> BookingWorkflowResult:
        workflow.logger.info(
            f'Starting BookingWorkflow Saga for booking_id={input_data.booking_id}'
        )

        # LIFO stack of compensation tuples: (activity_func, request_dto, step_name)
        compensations: List[Tuple[Any, Any, str]] = []

        try:
            # -----------------------------------------------------------
            # Step 1: Reserve Flight
            # -----------------------------------------------------------
            workflow.logger.info(f'Step 1: Reserving flight {input_data.flight_number}')
            flight_req = FlightReservationRequest(
                booking_id=input_data.booking_id,
                customer_id=input_data.customer_id,
                flight_number=input_data.flight_number,
                price=input_data.flight_price,
            )
            await workflow.execute_activity(
                reserve_flight_activity,
                flight_req,
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=FORWARD_RETRY_POLICY,
            )
            self.steps_completed.append('reserve_flight')

            # Register Flight compensation
            compensations.append((
                cancel_flight_activity,
                FlightCancellationRequest(
                    booking_id=input_data.booking_id,
                    reason=f'Saga rollback for booking {input_data.booking_id}',
                ),
                'cancel_flight',
            ))

            # -----------------------------------------------------------
            # Step 2: Reserve Hotel
            # -----------------------------------------------------------
            workflow.logger.info(f'Step 2: Reserving hotel {input_data.hotel_name}')
            hotel_req = HotelReservationRequest(
                booking_id=input_data.booking_id,
                customer_id=input_data.customer_id,
                hotel_name=input_data.hotel_name,
                price=input_data.hotel_price,
            )
            await workflow.execute_activity(
                reserve_hotel_activity,
                hotel_req,
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=FORWARD_RETRY_POLICY,
            )
            self.steps_completed.append('reserve_hotel')

            # Register Hotel compensation
            compensations.append((
                cancel_hotel_activity,
                HotelCancellationRequest(
                    booking_id=input_data.booking_id,
                    reason=f'Saga rollback for booking {input_data.booking_id}',
                ),
                'cancel_hotel',
            ))

            # -----------------------------------------------------------
            # Step 3: Charge Payment
            # -----------------------------------------------------------
            workflow.logger.info(
                f'Step 3: Charging ${input_data.total_amount} from customer {input_data.customer_id}'
            )
            payment_req = PaymentChargeRequest(
                booking_id=input_data.booking_id,
                customer_id=input_data.customer_id,
                amount=input_data.total_amount,
            )
            await workflow.execute_activity(
                charge_payment_activity,
                payment_req,
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=FORWARD_RETRY_POLICY,
            )
            self.steps_completed.append('charge_payment')

            # Register Payment refund compensation
            compensations.append((
                refund_payment_activity,
                PaymentRefundRequest(
                    booking_id=input_data.booking_id,
                    reason=f'Saga rollback for booking {input_data.booking_id}',
                ),
                'refund_payment',
            ))

            # -----------------------------------------------------------
            # Step 4: Confirm Reservations
            # -----------------------------------------------------------
            workflow.logger.info('Step 4: Finalizing and confirming reservations')
            await workflow.execute_activity(
                confirm_flight_activity,
                FlightConfirmationRequest(booking_id=input_data.booking_id),
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=FORWARD_RETRY_POLICY,
            )
            self.steps_completed.append('confirm_flight')

            await workflow.execute_activity(
                confirm_hotel_activity,
                HotelConfirmationRequest(booking_id=input_data.booking_id),
                start_to_close_timeout=timedelta(seconds=10),
                retry_policy=FORWARD_RETRY_POLICY,
            )
            self.steps_completed.append('confirm_hotel')

            workflow.logger.info(
                f'BookingWorkflow completed successfully for {input_data.booking_id}'
            )
            return BookingWorkflowResult(
                booking_id=input_data.booking_id,
                customer_id=input_data.customer_id,
                status='CONFIRMED',
                total_amount=input_data.total_amount,
                steps_completed=self.steps_completed,
                compensations_executed=[],
                error_message=None,
            )

        except Exception as exc:
            # Extract underlying cause message if wrapped in ActivityError
            error_msg = str(exc)
            if hasattr(exc, 'cause') and exc.cause:
                error_msg = str(exc.cause)

            workflow.logger.error(
                f'BookingWorkflow encountered failure at step {self.steps_completed[-1] if self.steps_completed else "start"}: {error_msg}'
            )
            workflow.logger.info(
                f'Initiating Saga compensations (LIFO order: {len(compensations)} action(s))'
            )

            # Rollback registered compensations in reverse order (LIFO)
            for comp_func, comp_arg, comp_name in reversed(compensations):
                try:
                    workflow.logger.warning(f'Executing compensation: {comp_name}')
                    await workflow.execute_activity(
                        comp_func,
                        comp_arg,
                        start_to_close_timeout=timedelta(seconds=15),
                        retry_policy=COMPENSATION_RETRY_POLICY,
                    )
                    self.compensations_executed.append(comp_name)
                except Exception as comp_exc:
                    workflow.logger.critical(
                        f'Critical error executing compensation {comp_name}: {comp_exc}'
                    )

            return BookingWorkflowResult(
                booking_id=input_data.booking_id,
                customer_id=input_data.customer_id,
                status='COMPENSATED',
                total_amount=input_data.total_amount,
                steps_completed=self.steps_completed,
                compensations_executed=self.compensations_executed,
                error_message=error_msg,
            )

"""
Core Booking Dispatcher.
Mediates between user interfaces (CLI, Web UI) and the underlying workflow orchestrators.
"""

import os
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from models import BookingRequest, BookingResponse, OrchestratorType
from scenarios import resolve_booking_payload


TEMPORAL_HOST = os.getenv('TEMPORAL_HOST', 'localhost:7233')
TEMPORAL_NAMESPACE = os.getenv('TEMPORAL_NAMESPACE', 'layover')
TEMPORAL_TASK_QUEUE = os.getenv('TEMPORAL_TASK_QUEUE', 'booking-task-queue')
TEMPORAL_WEB_UI = os.getenv('TEMPORAL_WEB_UI', 'http://localhost:8233')


async def dispatch_booking(request: BookingRequest) -> BookingResponse:
    """Dispatches a travel booking request to the selected orchestrator."""
    payload = resolve_booking_payload(request)
    booking_id = payload['booking_id']

    if request.orchestrator == OrchestratorType.TEMPORAL:
        try:
            client = await Client.connect(
                TEMPORAL_HOST,
                namespace=TEMPORAL_NAMESPACE,
                data_converter=pydantic_data_converter,
            )

            result = await client.execute_workflow(
                'BookingWorkflow',
                payload,
                id=booking_id,
                task_queue=TEMPORAL_TASK_QUEUE,
            )

            # Extract fields whether result is a Pydantic model or dict
            res_dict = result.model_dump() if hasattr(result, 'model_dump') else dict(result)

            return BookingResponse(
                booking_id=booking_id,
                orchestrator='temporal',
                scenario=request.scenario.value,
                status=res_dict.get('status', 'UNKNOWN'),
                total_amount=res_dict.get('total_amount', payload['total_amount']),
                steps_completed=res_dict.get('steps_completed', []),
                compensations_executed=res_dict.get('compensations_executed', []),
                error_message=res_dict.get('error_message'),
                temporal_ui_url=f'{TEMPORAL_WEB_UI}/namespaces/{TEMPORAL_NAMESPACE}/workflows/{booking_id}',
            )

        except Exception as exc:
            return BookingResponse(
                booking_id=booking_id,
                orchestrator='temporal',
                scenario=request.scenario.value,
                status='FAILED',
                total_amount=payload['total_amount'],
                steps_completed=[],
                compensations_executed=[],
                error_message=f'Temporal submission error: {exc}',
                temporal_ui_url=f'{TEMPORAL_WEB_UI}/namespaces/{TEMPORAL_NAMESPACE}/workflows/{booking_id}',
            )

    elif request.orchestrator == OrchestratorType.NAIVE:
        # Placeholder for Cycle 4
        return BookingResponse(
            booking_id=booking_id,
            orchestrator='naive',
            scenario=request.scenario.value,
            status='FAILED',
            total_amount=payload['total_amount'],
            steps_completed=[],
            compensations_executed=[],
            error_message='Naive coordinator will be implemented in Cycle 4.',
        )

    raise ValueError(f'Unsupported orchestrator: {request.orchestrator}')

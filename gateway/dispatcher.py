"""
Core Booking Dispatcher.
Mediates between user interfaces (CLI, Web UI) and the underlying workflow orchestrators.
"""

import os
from abc import ABC, abstractmethod
from typing import Any

from layover_naive.coordinator import NaiveSagaCoordinator
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter

from models import BookingRequest, BookingResponse, OrchestratorType
from scenarios import resolve_booking_payload


TEMPORAL_HOST = os.getenv('TEMPORAL_HOST', 'localhost:7233')
TEMPORAL_NAMESPACE = os.getenv('TEMPORAL_NAMESPACE', 'layover')
TEMPORAL_TASK_QUEUE = os.getenv('TEMPORAL_TASK_QUEUE', 'booking-task-queue')
TEMPORAL_WEB_UI = os.getenv('TEMPORAL_WEB_UI', 'http://localhost:8233')


class SagaOrchestratorStrategy(ABC):
    """Common engine contract retaining gateway metadata alongside the resolved payload."""

    @abstractmethod
    async def execute(self, request: BookingRequest, payload: dict[str, Any]) -> BookingResponse:
        """Execute a single booking without storing request-specific state on the strategy."""


class TemporalSagaStrategy(SagaOrchestratorStrategy):
    """Durable execution delegated to Temporal; existing workflow behavior is unchanged."""

    async def execute(self, request: BookingRequest, payload: dict[str, Any]) -> BookingResponse:
        booking_id = payload['booking_id']
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


class NaiveSagaStrategy(SagaOrchestratorStrategy):
    """In-process baseline: killing the gateway destroys its volatile compensation stack."""

    async def execute(self, request: BookingRequest, payload: dict[str, Any]) -> BookingResponse:
        try:
            # A fresh coordinator per request, never a stack stored in the shared registry.
            result = await NaiveSagaCoordinator().execute(payload)
            result_data = result.model_dump() if hasattr(result, 'model_dump') else dict(result)

            return BookingResponse(
                booking_id=payload['booking_id'],
                orchestrator='naive',
                scenario=request.scenario.value,
                status=result_data['status'],
                total_amount=result_data['total_amount'],
                steps_completed=result_data.get('steps_completed', []),
                compensations_executed=result_data.get('compensations_executed', []),
                error_message=result_data.get('error_message'),
                temporal_ui_url=None,
            )
        except Exception as exc:
            return BookingResponse(
                booking_id=payload['booking_id'],
                orchestrator='naive',
                scenario=request.scenario.value,
                status='FAILED',
                total_amount=payload['total_amount'],
                error_message=f'Naive execution error: {exc}. No complete result is available; reconciliation may be required.',
            )


STRATEGIES: dict[OrchestratorType, SagaOrchestratorStrategy] = {
    OrchestratorType.TEMPORAL: TemporalSagaStrategy(),
    OrchestratorType.NAIVE: NaiveSagaStrategy(),
}


async def dispatch_booking(request: BookingRequest) -> BookingResponse:
    """Resolve the booking once and select its engine via the Strategy registry."""
    payload = resolve_booking_payload(request)
    strategy = STRATEGIES.get(request.orchestrator)
    if strategy is None:
        raise ValueError(f'Unsupported orchestrator: {request.orchestrator}')

    return await strategy.execute(request, payload)

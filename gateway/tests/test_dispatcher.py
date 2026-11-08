"""Exercise the Strategy context itself, not a mocked dispatch_booking endpoint."""

import json
from unittest.mock import AsyncMock, patch

import httpx
import pytest

import dispatcher
from layover_naive.coordinator import NaiveSagaCoordinator
from models import BookingRequest, BookingResponse, OrchestratorType, ScenarioType
from scenarios import resolve_booking_payload


def booking_response(request, payload):
    return BookingResponse(
        booking_id=payload['booking_id'],
        orchestrator=request.orchestrator.value,
        scenario=request.scenario.value,
        status='CONFIRMED',
        total_amount=payload['total_amount'],
    )


@pytest.mark.parametrize('engine', list(OrchestratorType))
async def test_dispatcher_resolves_once_and_selects_only_the_requested_strategy(engine, monkeypatch):
    request = BookingRequest(orchestrator=engine, scenario='fail_payment', booking_id='bk-selected')
    payload = resolve_booking_payload(request)
    active = AsyncMock(spec=dispatcher.SagaOrchestratorStrategy)
    inactive = AsyncMock(spec=dispatcher.SagaOrchestratorStrategy)
    active.execute.return_value = booking_response(request, payload)
    strategies = {key: active if key == engine else inactive for key in OrchestratorType}
    monkeypatch.setattr(dispatcher, 'STRATEGIES', strategies)

    with patch('dispatcher.resolve_booking_payload', wraps=resolve_booking_payload) as resolve:
        result = await dispatcher.dispatch_booking(request)

    resolve.assert_called_once_with(request)
    active.execute.assert_awaited_once_with(request, payload)
    inactive.execute.assert_not_awaited()
    assert result.scenario == 'fail_payment'


def test_registry_uses_concrete_strategies_with_an_abstract_interface():
    with pytest.raises(TypeError):
        dispatcher.SagaOrchestratorStrategy()
    assert isinstance(dispatcher.STRATEGIES[OrchestratorType.TEMPORAL], dispatcher.TemporalSagaStrategy)
    assert isinstance(dispatcher.STRATEGIES[OrchestratorType.NAIVE], dispatcher.NaiveSagaStrategy)


@pytest.mark.parametrize('scenario, expected_status, expected_compensations', [
    (ScenarioType.HAPPY_PATH, 'CONFIRMED', []),
    (ScenarioType.FAIL_HOTEL, 'COMPENSATED', ['cancel_flight']),
    (ScenarioType.FAIL_PAYMENT, 'COMPENSATED', ['cancel_hotel', 'cancel_flight']),
])
async def test_naive_strategy_runs_real_coordinator_without_temporal(scenario, expected_status, expected_compensations):
    request = BookingRequest(orchestrator='naive', scenario=scenario, booking_id='bk-naive-dispatch')
    calls = []

    def handler(http_request):
        payload = json.loads(http_request.content)
        path = http_request.url.path
        calls.append((path, payload))
        if scenario == ScenarioType.FAIL_HOTEL and http_request.url.port == 8002:
            assert payload['price'] == -1.0
            return httpx.Response(422, json={'detail': 'Hotel validation failed'})
        if scenario == ScenarioType.FAIL_PAYMENT and path == '/charge':
            return httpx.Response(400, json={'detail': 'Insufficient funds'})
        status = {'/reserve': 'RESERVED', '/charge': 'CHARGED', '/confirm': 'CONFIRMED', '/cancel': 'CANCELLED'}[path]
        return httpx.Response(201 if path in ('/reserve', '/charge') else 200, json={**payload, 'status': status})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        coordinator = NaiveSagaCoordinator(client=client)
        with (
            patch('dispatcher.NaiveSagaCoordinator', return_value=coordinator),
            patch('dispatcher.Client.connect', new_callable=AsyncMock) as temporal_connect,
        ):
            result = await dispatcher.dispatch_booking(request)

    assert result.booking_id == request.booking_id
    assert result.orchestrator == 'naive'
    assert result.scenario == scenario.value
    assert result.status == expected_status
    assert result.compensations_executed == expected_compensations
    assert result.temporal_ui_url is None
    assert result.total_amount == resolve_booking_payload(request)['total_amount']
    temporal_connect.assert_not_awaited()


async def test_custom_scenario_and_fields_are_preserved_for_naive():
    request = BookingRequest(
        orchestrator='naive', scenario='custom', booking_id='bk-custom', customer_id='custom-user',
        flight_number='CUSTOM-1', flight_price=12.5, hotel_name='Custom hotel', hotel_price=10.0,
    )
    coordinator = AsyncMock(spec=NaiveSagaCoordinator)
    coordinator.execute.return_value = {
        'booking_id': 'bk-custom', 'status': 'CONFIRMED', 'total_amount': 22.5,
        'steps_completed': ['reserve_flight', 'reserve_hotel', 'charge_payment', 'confirm_flight', 'confirm_hotel'],
        'compensations_executed': [], 'error_message': None,
    }
    with patch('dispatcher.NaiveSagaCoordinator', return_value=coordinator):
        result = await dispatcher.dispatch_booking(request)

    coordinator.execute.assert_awaited_once_with(resolve_booking_payload(request))
    assert result.scenario == 'custom'
    assert result.total_amount == 22.5


@pytest.mark.parametrize('model_result', [False, True])
async def test_temporal_strategy_preserves_invocation_configuration_and_result_mapping(model_result):
    request = BookingRequest(orchestrator='temporal', scenario='fail_payment', booking_id='bk-temporal-dispatch')
    payload = resolve_booking_payload(request)
    result_data = {
        'status': 'COMPENSATED', 'total_amount': 2500.0,
        'steps_completed': ['reserve_flight', 'reserve_hotel'],
        'compensations_executed': ['cancel_hotel', 'cancel_flight'],
        'error_message': 'Payment declined',
    }
    client = AsyncMock()
    if model_result:
        from pydantic import BaseModel

        class WorkflowResult(BaseModel):
            status: str
            total_amount: float
            steps_completed: list[str]
            compensations_executed: list[str]
            error_message: str

        client.execute_workflow.return_value = WorkflowResult(**result_data)
    else:
        client.execute_workflow.return_value = result_data

    with patch('dispatcher.Client.connect', new_callable=AsyncMock, return_value=client) as connect:
        result = await dispatcher.dispatch_booking(request)

    connect.assert_awaited_once_with(
        dispatcher.TEMPORAL_HOST, namespace=dispatcher.TEMPORAL_NAMESPACE,
        data_converter=dispatcher.pydantic_data_converter,
    )
    client.execute_workflow.assert_awaited_once_with(
        'BookingWorkflow', payload, id='bk-temporal-dispatch', task_queue=dispatcher.TEMPORAL_TASK_QUEUE,
    )
    assert result.orchestrator == 'temporal'
    assert result.scenario == 'fail_payment'
    assert result.status == 'COMPENSATED'
    assert result.steps_completed == result_data['steps_completed']
    assert result.compensations_executed == result_data['compensations_executed']
    assert '/workflows/bk-temporal-dispatch' in result.temporal_ui_url


async def test_temporal_connection_failure_retains_existing_response_contract():
    request = BookingRequest(booking_id='bk-unavailable')
    with patch('dispatcher.Client.connect', new_callable=AsyncMock, side_effect=RuntimeError('cluster unavailable')):
        result = await dispatcher.dispatch_booking(request)

    assert result.status == 'FAILED'
    assert result.steps_completed == result.compensations_executed == []
    assert result.error_message == 'Temporal submission error: cluster unavailable'

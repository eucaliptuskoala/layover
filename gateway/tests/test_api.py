"""
Integration and Unit Tests for the Layover Gateway FastAPI Application.
Tests health probes, scenario catalogs, booking dispatching, and CORS configuration.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from main import app
from models import (
    BookingResponse,
    OrchestratorType,
    ServiceHealth,
    SystemHealthReport,
)


@pytest.fixture
async def test_client():
    """Provides an isolated HTTP client bound to the FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        yield client


@pytest.mark.asyncio
async def test_root_endpoint(test_client: AsyncClient):
    """Verifies gateway root index returns operational status and documentation link."""
    response = await test_client.get('/')

    assert response.status_code == 200
    data = response.json()
    assert data['service'] == 'Layover API Gateway'
    assert data['status'] == 'OPERATIONAL'
    assert data['version'] == '1.0.0'


@pytest.mark.asyncio
async def test_list_scenarios_endpoint(test_client: AsyncClient):
    """Verifies that available testing scenarios are cataloged with defaults and descriptions."""
    response = await test_client.get('/api/scenarios')

    assert response.status_code == 200
    scenarios = response.json()
    assert isinstance(scenarios, list)
    assert len(scenarios) >= 3

    keys = {s['key'] for s in scenarios}
    assert 'happy_path' in keys
    assert 'fail_hotel' in keys
    assert 'fail_payment' in keys

    # Verify scenario schema
    sample = scenarios[0]
    assert 'key' in sample
    assert 'name' in sample
    assert 'description' in sample
    assert 'expected_total' in sample


@pytest.mark.asyncio
async def test_health_endpoint_healthy(test_client: AsyncClient):
    """Verifies /api/health when all microservices report UP."""
    mock_report = SystemHealthReport(
        overall_status='HEALTHY',
        services=[
            ServiceHealth(name='Flight Service', url='http://localhost:8001', status='UP', latency_ms=12.4),
            ServiceHealth(name='Hotel Service', url='http://localhost:8002', status='UP', latency_ms=15.1),
            ServiceHealth(name='Payment Service', url='http://localhost:8003', status='UP', latency_ms=18.0),
            ServiceHealth(name='Temporal Engine', url='grpc://localhost:7233', status='UP', latency_ms=5.2),
        ],
    )

    with patch('main.check_all_services', new=AsyncMock(return_value=mock_report)):
        response = await test_client.get('/api/health')

        assert response.status_code == 200
        data = response.json()
        assert data['overall_status'] == 'HEALTHY'
        assert len(data['services']) == 4
        assert all(s['status'] == 'UP' for s in data['services'])


@pytest.mark.asyncio
async def test_health_endpoint_degraded(test_client: AsyncClient):
    """Verifies /api/health returns DEGRADED without crashing if a service is down."""
    mock_report = SystemHealthReport(
        overall_status='DEGRADED',
        services=[
            ServiceHealth(name='Flight Service', url='http://localhost:8001', status='UP', latency_ms=12.4),
            ServiceHealth(name='Hotel Service', url='http://localhost:8002', status='DOWN', error='Connection refused'),
        ],
    )

    with patch('main.check_all_services', new=AsyncMock(return_value=mock_report)):
        response = await test_client.get('/health')

        assert response.status_code == 200
        data = response.json()
        assert data['overall_status'] == 'DEGRADED'


@pytest.mark.asyncio
async def test_create_booking_success(test_client: AsyncClient):
    """Verifies successful booking dispatch returns structured BookingResponse."""
    mock_response = BookingResponse(
        booking_id='bk-test1234',
        orchestrator='temporal',
        scenario='happy_path',
        status='CONFIRMED',
        total_amount=400.0,
        steps_completed=['reserve_flight', 'reserve_hotel', 'charge_payment'],
        compensations_executed=[],
        temporal_ui_url='http://localhost:8233/namespaces/layover/workflows/bk-test1234',
    )

    with patch('main.dispatch_booking', new=AsyncMock(return_value=mock_response)):
        payload = {
            'orchestrator': 'temporal',
            'scenario': 'happy_path',
            'customer_id': 'user_1',
        }
        response = await test_client.post('/api/bookings', json=payload)

        assert response.status_code == 200
        data = response.json()
        assert data['booking_id'] == 'bk-test1234'
        assert data['status'] == 'CONFIRMED'
        assert data['total_amount'] == 400.0
        assert len(data['steps_completed']) == 3


@pytest.mark.asyncio
async def test_create_booking_validation_error(test_client: AsyncClient):
    """Verifies that malformed payload returns HTTP 422 Unprocessable Entity."""
    # Invalid orchestrator type
    payload = {
        'orchestrator': 'invalid_orchestrator',
        'scenario': 'happy_path',
    }
    response = await test_client.post('/api/bookings', json=payload)

    assert response.status_code == 422


@pytest.mark.parametrize('engine', list(OrchestratorType))
async def test_booking_endpoint_uses_strategy_selection(test_client: AsyncClient, engine, monkeypatch):
    import dispatcher

    strategy = AsyncMock(spec=dispatcher.SagaOrchestratorStrategy)
    strategy.execute.return_value = BookingResponse(
        booking_id='bk-api-strategy', orchestrator=engine.value, scenario='fail_hotel',
        status='COMPENSATED', total_amount=299.0,
        steps_completed=['reserve_flight'], compensations_executed=['cancel_flight'],
    )
    monkeypatch.setitem(dispatcher.STRATEGIES, engine, strategy)

    response = await test_client.post('/api/bookings', json={
        'booking_id': 'bk-api-strategy', 'orchestrator': engine.value, 'scenario': 'fail_hotel',
    })

    assert response.status_code == 200
    assert response.json()['orchestrator'] == engine.value
    assert response.json()['scenario'] == 'fail_hotel'
    assert response.json()['compensations_executed'] == ['cancel_flight']
    strategy.execute.assert_awaited_once()
    assert strategy.execute.call_args.args[1]['hotel_price'] == -1.0


@pytest.mark.asyncio
async def test_cors_preflight(test_client: AsyncClient):
    """Verifies CORS middleware answers preflight OPTIONS request for frontend origin."""
    headers = {
        'Origin': 'http://localhost:5173',
        'Access-Control-Request-Method': 'POST',
        'Access-Control-Request-Headers': 'Content-Type',
    }
    response = await test_client.options('/api/bookings', headers=headers)

    assert response.status_code == 200
    assert response.headers.get('access-control-allow-origin') in ('*', 'http://localhost:5173')


@pytest.mark.asyncio
async def test_audit_endpoint_detects_stranded_hold(test_client: AsyncClient, monkeypatch):
    """Verifies that the audit endpoint queries microservices and flags stranded holds."""
    import httpx

    original_get = httpx.AsyncClient.get

    async def mock_get(self, url, *args, **kwargs):
        url_str = str(url)
        if '8001' in url_str:  # Flight service
            return httpx.Response(
                status_code=200,
                json={
                    'booking_id': 'bk-stranded-test',
                    'flight_number': 'LH-204',
                    'status': 'RESERVED',
                },
            )
        elif '8002' in url_str or '8003' in url_str:  # Hotel & Payment services
            return httpx.Response(status_code=404, json={'detail': 'Not found'})
        return await original_get(self, url, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, 'get', mock_get)

    response = await test_client.get('/api/bookings/bk-stranded-test/audit')

    assert response.status_code == 200
    data = response.json()
    assert data['booking_id'] == 'bk-stranded-test'
    assert data['has_stranded_records'] is True
    assert data['flight']['status'] == 'RESERVED'
    assert data['flight']['is_stranded'] is True
    assert data['flight']['database_file'] == 'flight.db'
    assert data['hotel']['status'] == 'NOT_FOUND'
    assert data['hotel']['is_stranded'] is False
    assert data['payment']['status'] == 'NOT_FOUND'
    assert data['payment']['is_stranded'] is False
    assert 'flight.db' in data['summary']


@pytest.mark.asyncio
async def test_audit_endpoint_consistent_state(test_client: AsyncClient, monkeypatch):
    """Verifies that the audit endpoint reports clean state when reservations are cancelled."""
    import httpx

    original_get = httpx.AsyncClient.get

    async def mock_get(self, url, *args, **kwargs):
        url_str = str(url)
        if '8001' in url_str:
            return httpx.Response(
                status_code=200,
                json={'booking_id': 'bk-clean-test', 'status': 'CANCELLED'},
            )
        elif '8002' in url_str or '8003' in url_str:
            return httpx.Response(status_code=404, json={'detail': 'Not found'})
        return await original_get(self, url, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, 'get', mock_get)

    response = await test_client.get('/api/bookings/bk-clean-test/audit')

    assert response.status_code == 200
    data = response.json()
    assert data['booking_id'] == 'bk-clean-test'
    assert data['has_stranded_records'] is False
    assert data['flight']['status'] == 'CANCELLED'
    assert data['flight']['is_stranded'] is False
    assert data['summary'] == 'All service databases are in a consistent state.'

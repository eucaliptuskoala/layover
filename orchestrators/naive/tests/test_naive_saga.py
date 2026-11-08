"""Contract and ordering tests without live services or persistent coordinator state."""

import asyncio
import json

import httpx
import pytest

from layover_naive.coordinator import NaiveSagaCoordinator


@pytest.fixture
def booking_payload():
    return {
        'booking_id': 'bk-naive-test',
        'customer_id': 'user_1',
        'flight_number': 'LH-204',
        'flight_price': 250.0,
        'hotel_name': 'Grand Palace Hotel',
        'hotel_price': 150.0,
    }


def acknowledge(request: httpx.Request) -> httpx.Response:
    payload = json.loads(request.content)
    action = request.url.path
    state = {
        '/reserve': 'RESERVED',
        '/charge': 'CHARGED',
        '/confirm': 'CONFIRMED',
        '/cancel': 'CANCELLED',
        '/refund': 'REFUNDED',
    }[action]
    status_code = 201 if action in ('/reserve', '/charge') else 200
    return httpx.Response(status_code, json={**payload, 'status': state})


async def execute_with_handler(payload, handler):
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        return await NaiveSagaCoordinator(client=client).execute(payload)


async def test_happy_path_preserves_forward_order_and_service_payloads(booking_payload):
    calls = []

    def handler(request):
        calls.append((str(request.url), json.loads(request.content)))
        return acknowledge(request)

    result = await execute_with_handler(booking_payload, handler)

    assert result.status == 'CONFIRMED'
    assert result.booking_id == booking_payload['booking_id']
    assert result.total_amount == 400.0
    assert result.steps_completed == [
        'reserve_flight', 'reserve_hotel', 'charge_payment', 'confirm_flight', 'confirm_hotel',
    ]
    assert result.compensations_executed == []
    assert result.error_message is None
    assert [url for url, _ in calls] == [
        'http://localhost:8001/reserve',
        'http://localhost:8002/reserve',
        'http://localhost:8003/charge',
        'http://localhost:8001/confirm',
        'http://localhost:8002/confirm',
    ]
    assert calls[0][1] == {
        'booking_id': 'bk-naive-test', 'customer_id': 'user_1',
        'flight_number': 'LH-204', 'price': 250.0,
    }
    assert calls[1][1] == {
        'booking_id': 'bk-naive-test', 'customer_id': 'user_1',
        'hotel_name': 'Grand Palace Hotel', 'price': 150.0,
    }
    assert calls[2][1] == {
        'booking_id': 'bk-naive-test', 'customer_id': 'user_1', 'amount': 400.0,
    }
    assert calls[3][1] == calls[4][1] == {'booking_id': 'bk-naive-test'}


async def test_hotel_422_reaches_service_with_negative_price_and_only_cancels_flight(booking_payload):
    calls = []
    booking_payload['hotel_price'] = -1.0

    def handler(request):
        calls.append((request.url.port, request.url.path))
        if request.url.port == 8002:
            assert json.loads(request.content)['price'] == -1.0
            return httpx.Response(422, json={'detail': 'Hotel price must be positive'})
        return acknowledge(request)

    result = await execute_with_handler(booking_payload, handler)

    assert result.status == 'COMPENSATED'
    assert result.total_amount == 249.0
    assert result.steps_completed == ['reserve_flight']
    assert result.compensations_executed == ['cancel_flight']
    assert 'reserve_hotel' in result.error_message
    assert '422' in result.error_message
    assert calls == [(8001, '/reserve'), (8002, '/reserve'), (8001, '/cancel')]


async def test_payment_400_cancels_hotel_then_flight_without_refund(booking_payload):
    calls = []

    def handler(request):
        calls.append((request.url.port, request.url.path))
        if request.url.path == '/charge':
            return httpx.Response(400, json={'detail': 'Insufficient funds'})
        return acknowledge(request)

    result = await execute_with_handler(booking_payload, handler)

    assert result.status == 'COMPENSATED'
    assert result.steps_completed == ['reserve_flight', 'reserve_hotel']
    assert result.compensations_executed == ['cancel_hotel', 'cancel_flight']
    assert 'Insufficient funds' in result.error_message
    assert calls == [
        (8001, '/reserve'), (8002, '/reserve'), (8003, '/charge'),
        (8002, '/cancel'), (8001, '/cancel'),
    ]


async def test_confirmation_rejection_refunds_payment_before_cancelling_reservations(booking_payload):
    calls = []

    def handler(request):
        calls.append((request.url.port, request.url.path))
        if request.url.path == '/confirm':
            return httpx.Response(409, json={'detail': 'Confirmation rejected without a transition'})
        return acknowledge(request)

    result = await execute_with_handler(booking_payload, handler)

    assert result.status == 'COMPENSATED'
    assert result.steps_completed == ['reserve_flight', 'reserve_hotel', 'charge_payment']
    assert result.compensations_executed == ['refund_payment', 'cancel_hotel', 'cancel_flight']
    assert calls[-3:] == [(8003, '/refund'), (8002, '/cancel'), (8001, '/cancel')]


@pytest.mark.parametrize('failed_compensation', ['refund_payment', 'cancel_hotel', 'cancel_flight'])
async def test_rollback_continues_after_a_failed_compensation(booking_payload, failed_compensation):
    calls = []
    actions = {(8003, '/refund'): 'refund_payment', (8002, '/cancel'): 'cancel_hotel',
               (8001, '/cancel'): 'cancel_flight'}

    def handler(request):
        action = actions.get((request.url.port, request.url.path))
        if action:
            calls.append(action)
        if request.url.path == '/confirm' or action == failed_compensation:
            return httpx.Response(409, json={'detail': 'State transition rejected'})
        return acknowledge(request)

    result = await execute_with_handler(booking_payload, handler)

    assert result.status == 'FAILED'
    assert calls == ['refund_payment', 'cancel_hotel', 'cancel_flight']
    assert result.compensations_executed == [action for action in calls if action != failed_compensation]
    assert 'confirm_flight' in result.error_message
    assert failed_compensation in result.error_message
    assert 'reconciliation' in result.error_message.lower()


async def test_hotel_confirmation_failure_reports_uncancellable_confirmed_flight(booking_payload):
    def handler(request):
        if (request.url.port, request.url.path) == (8002, '/confirm'):
            return httpx.Response(409, json={'detail': 'Hotel confirmation rejected'})
        if (request.url.port, request.url.path) == (8001, '/cancel'):
            return httpx.Response(409, json={'detail': 'Cannot cancel confirmed booking'})
        return acknowledge(request)

    result = await execute_with_handler(booking_payload, handler)

    assert result.status == 'FAILED'
    assert result.steps_completed[-1] == 'confirm_flight'
    assert result.compensations_executed == ['refund_payment', 'cancel_hotel']
    assert 'Cannot cancel confirmed booking' in result.error_message


@pytest.mark.parametrize('failure', ['timeout', 'server_error', 'malformed_success', 'wrong_booking', 'wrong_state'])
async def test_uncertain_payment_outcome_never_claims_complete_rollback(booking_payload, failure):
    calls = []

    def handler(request):
        calls.append((request.url.port, request.url.path))
        if request.url.path == '/charge':
            if failure == 'timeout':
                raise httpx.ReadTimeout('Response lost after possible commit', request=request)
            if failure == 'server_error':
                return httpx.Response(500, text='Response generation failed')
            if failure == 'malformed_success':
                return httpx.Response(201, text='not JSON')
            return httpx.Response(201, json={
                'booking_id': 'bk-other' if failure == 'wrong_booking' else booking_payload['booking_id'],
                'status': 'REFUNDED' if failure == 'wrong_state' else 'CHARGED',
            })
        return acknowledge(request)

    result = await execute_with_handler(booking_payload, handler)

    assert result.status == 'FAILED'
    assert result.steps_completed == ['reserve_flight', 'reserve_hotel']
    assert result.compensations_executed == ['cancel_hotel', 'cancel_flight']
    assert 'unknown' in result.error_message.lower()
    assert 'charge_payment' in result.error_message
    assert calls.count((8003, '/charge')) == 1
    assert all(path not in ('/confirm', '/refund') for _, path in calls)


async def test_first_step_rejection_is_failed_without_completed_actions(booking_payload):
    result = await execute_with_handler(
        booking_payload, lambda request: httpx.Response(422, json={'detail': 'Invalid flight'}),
    )

    assert result.status == 'FAILED'
    assert result.steps_completed == result.compensations_executed == []


async def test_environment_urls_and_rounding_are_used(booking_payload, monkeypatch):
    monkeypatch.setenv('FLIGHT_SERVICE_URL', 'http://flight.test:9001/')
    monkeypatch.setenv('HOTEL_SERVICE_URL', 'http://hotel.test:9002/')
    monkeypatch.setenv('PAYMENT_SERVICE_URL', 'http://payment.test:9003/')
    booking_payload.update(flight_price=12.345, hotel_price=1.0, total_amount=999.0)
    calls = []

    def handler(request):
        calls.append(str(request.url))
        if request.url.path == '/charge':
            assert json.loads(request.content)['amount'] == 13.35
        return acknowledge(request)

    result = await execute_with_handler(booking_payload, handler)

    assert result.total_amount == 13.35
    assert calls == [
        'http://flight.test:9001/reserve', 'http://hotel.test:9002/reserve',
        'http://payment.test:9003/charge', 'http://flight.test:9001/confirm',
        'http://hotel.test:9002/confirm',
    ]


async def test_concurrent_runs_on_one_coordinator_have_separate_stacks(booking_payload):
    first_payment_started = asyncio.Event()
    second_rollback_finished = asyncio.Event()
    cancellations = []

    async def handler(request):
        booking_id = json.loads(request.content)['booking_id']
        if request.url.path == '/charge':
            if booking_id == 'bk-first':
                first_payment_started.set()
                await second_rollback_finished.wait()
            else:
                await first_payment_started.wait()
            return httpx.Response(400, json={'detail': 'Insufficient funds'})
        if request.url.path == '/cancel':
            cancellations.append((booking_id, request.url.port))
            if booking_id == 'bk-second' and request.url.port == 8001:
                second_rollback_finished.set()
        return acknowledge(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        coordinator = NaiveSagaCoordinator(client=client)
        first, second = await asyncio.wait_for(asyncio.gather(
            coordinator.execute({**booking_payload, 'booking_id': 'bk-first'}),
            coordinator.execute({**booking_payload, 'booking_id': 'bk-second'}),
        ), timeout=5)

    assert first.status == second.status == 'COMPENSATED'
    assert first.compensations_executed == second.compensations_executed == ['cancel_hotel', 'cancel_flight']
    assert cancellations == [
        ('bk-second', 8002), ('bk-second', 8001), ('bk-first', 8002), ('bk-first', 8001),
    ]

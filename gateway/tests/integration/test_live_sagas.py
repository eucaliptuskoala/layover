"""Exercise the actual gateway, workers, service HTTP contracts, and isolated databases."""

import uuid

import httpx
import pytest


pytestmark = pytest.mark.integration


@pytest.mark.parametrize('engine', ['naive', 'temporal'])
@pytest.mark.parametrize('scenario', ['happy_path', 'fail_hotel', 'fail_payment'])
async def test_both_engines_against_real_services(live_stack, engine, scenario):
    booking_id = f'bk-live-{uuid.uuid4().hex}'
    async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
        response = await client.post(f'{live_stack.gateway_url}/api/bookings', json={
            'booking_id': booking_id, 'orchestrator': engine, 'scenario': scenario,
        })
        response.raise_for_status()
        result = response.json()
        assert result['booking_id'] == booking_id
        assert result['orchestrator'] == engine
        assert result['scenario'] == scenario
        assert result['status'] == ('CONFIRMED' if scenario == 'happy_path' else 'COMPENSATED')
        assert (result['temporal_ui_url'] is None) == (engine == 'naive')

        flight = await client.get(f'{live_stack.urls["flight"]}/reservations/{booking_id}')
        hotel = await client.get(f'{live_stack.urls["hotel"]}/reservations/{booking_id}')
        payment = await client.get(f'{live_stack.urls["payment"]}/payment/{booking_id}')
        account = await client.get(f'{live_stack.urls["payment"]}/account/user_1')
        flight.raise_for_status()
        account.raise_for_status()

        if scenario == 'happy_path':
            hotel.raise_for_status()
            payment.raise_for_status()
            assert flight.json()['status'] == hotel.json()['status'] == 'CONFIRMED'
            assert payment.json()['status'] == 'CHARGED'
            assert account.json()['balance'] == 600.0
            assert result['steps_completed'] == [
                'reserve_flight', 'reserve_hotel', 'charge_payment', 'confirm_flight', 'confirm_hotel',
            ]
            assert result['compensations_executed'] == []
        else:
            assert flight.json()['status'] == 'CANCELLED'
            assert payment.status_code == 404
            assert account.json()['balance'] == 1000.0
            if scenario == 'fail_hotel':
                assert hotel.status_code == 404
                assert result['steps_completed'] == ['reserve_flight']
                assert result['compensations_executed'] == ['cancel_flight']
                assert '422' in result['error_message']
            else:
                hotel.raise_for_status()
                assert hotel.json()['status'] == 'CANCELLED'
                assert result['steps_completed'] == ['reserve_flight', 'reserve_hotel']
                assert result['compensations_executed'] == ['cancel_hotel', 'cancel_flight']
                assert '400' in result['error_message']


async def test_naive_gateway_runs_without_a_temporal_server(naive_stack):
    async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
        response = await client.post(f'{naive_stack.gateway_url}/api/bookings', json={
            'orchestrator': 'naive', 'scenario': 'happy_path',
        })

    response.raise_for_status()
    assert response.json()['status'] == 'CONFIRMED'
    assert response.json()['temporal_ui_url'] is None

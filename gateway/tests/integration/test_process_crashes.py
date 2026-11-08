"""Crash only owned coordinator processes at a service-observed, deterministic barrier."""

import asyncio
import json
import uuid
from contextlib import suppress

import httpx
import pytest


pytestmark = pytest.mark.integration


async def service_snapshot(client, stack, booking_id):
    snapshot = {}
    for service, path in [('flight', 'reservations'), ('hotel', 'reservations'), ('payment', 'payment')]:
        response = await client.get(f'{stack.urls[service]}/{path}/{booking_id}')
        if response.status_code == 404:
            snapshot[service] = 'ABSENT'
        else:
            response.raise_for_status()
            snapshot[service] = response.json()['status']
    account = await client.get(f'{stack.urls["payment"]}/account/user_1')
    account.raise_for_status()
    snapshot['balance'] = account.json()['balance']
    return snapshot


@pytest.mark.parametrize('engine', ['naive', 'temporal'])
async def test_sigkill_after_reservations_exposes_volatile_state_loss(crash_stack, engine):
    booking_id = f'bk-crash-{engine}-{uuid.uuid4().hex}'
    async with httpx.AsyncClient(timeout=90, trust_env=False) as client:
        booking = asyncio.create_task(client.post(f'{crash_stack.gateway_url}/api/bookings', json={
            'booking_id': booking_id, 'orchestrator': engine, 'scenario': 'fail_payment',
        }))
        try:
            # /charge is intercepted BEFORE it reaches Payment. Both preceding HTTP
            # acknowledgments have been received, and the coordinator is now blocked.
            arrival = await client.get(f'{crash_stack.barrier_url}/test/wait-for-payment', timeout=30)
            arrival.raise_for_status()
            assert arrival.json()['booking_id'] == booking_id
            before = await service_snapshot(client, crash_stack, booking_id)
            assert before == {'flight': 'RESERVED', 'hotel': 'RESERVED', 'payment': 'ABSENT', 'balance': 1000.0}

            target = 'gateway' if engine == 'naive' else 'worker'
            killed_pid = crash_stack.kill(target)
            if engine == 'naive':
                with pytest.raises(httpx.RequestError):
                    await asyncio.wait_for(booking, timeout=10)
                await crash_stack.start_gateway()
            else:
                crash_stack.start_worker()

            release = await client.post(f'{crash_stack.barrier_url}/test/release')
            release.raise_for_status()
            forwarded = await client.get(f'{crash_stack.barrier_url}/test/wait-for-decline', timeout=30)
            forwarded.raise_for_status()
            assert forwarded.json()['status_code'] == 400

            if engine == 'temporal':
                response = await asyncio.wait_for(booking, timeout=75)
                response.raise_for_status()
                result = response.json()
                assert result['status'] == 'COMPENSATED'
                assert result['steps_completed'] == ['reserve_flight', 'reserve_hotel']
                assert result['compensations_executed'] == ['cancel_hotel', 'cancel_flight']
                history = await crash_stack.temporal_client.get_workflow_handle(booking_id).fetch_history()
                assert len(history.events) > 0

            after = await service_snapshot(client, crash_stack, booking_id)
            expected_state = 'RESERVED' if engine == 'naive' else 'CANCELLED'
            assert after == {
                'flight': expected_state, 'hotel': expected_state, 'payment': 'ABSENT', 'balance': 1000.0,
            }
            assert crash_stack.processes['temporal'].process.poll() is None
            print(json.dumps({
                'engine': engine, 'booking_id': booking_id,
                'killed_process': target, 'killed_pid': killed_pid,
                'checkpoint': 'before payment, after reservation acknowledgments',
                'before': before, 'after': after,
                'history_event_count': len(history.events) if engine == 'temporal' else None,
            }))
        finally:
            if not booking.done():
                booking.cancel()
            with suppress(asyncio.CancelledError, httpx.HTTPError):
                await booking

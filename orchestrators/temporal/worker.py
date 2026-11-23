"""
Temporal Worker process for Travel Booking Saga.
Listens on the booking-task-queue and executes BookingWorkflow and its associated activities.
"""

import asyncio
import os
from temporalio.client import Client
from temporalio.contrib.pydantic import pydantic_data_converter
from temporalio.worker import Worker

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
from metrics import generate_prometheus_metrics
from workflows import BookingWorkflow


TEMPORAL_HOST = os.getenv('TEMPORAL_HOST', 'localhost:7233')
TEMPORAL_NAMESPACE = os.getenv('TEMPORAL_NAMESPACE', 'layover')
TEMPORAL_TASK_QUEUE = os.getenv('TEMPORAL_TASK_QUEUE', 'booking-task-queue')
METRICS_PORT = int(os.getenv('METRICS_PORT', '8005'))


async def handle_metrics_request(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    """Lightweight HTTP handler serving Prometheus text metrics on port 8005."""
    try:
        await reader.read(1024)
        body = generate_prometheus_metrics('layover-worker')
        response = (
            f'HTTP/1.1 200 OK\r\n'
            f'Content-Type: text/plain; version=0.0.4\r\n'
            f'Content-Length: {len(body)}\r\n'
            f'Connection: close\r\n\r\n'
            f'{body}'
        )
        writer.write(response.encode('utf-8'))
        await writer.drain()
    except Exception:
        pass
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def run_worker() -> None:
    print(f'[Temporal Worker] Connecting to Temporal server at {TEMPORAL_HOST} (namespace: {TEMPORAL_NAMESPACE})...')
    client = await Client.connect(
        TEMPORAL_HOST,
        namespace=TEMPORAL_NAMESPACE,
        data_converter=pydantic_data_converter,
    )
    print('[Temporal Worker] Connected successfully.')

    metrics_server = await asyncio.start_server(handle_metrics_request, '0.0.0.0', METRICS_PORT)
    print(f'[Temporal Worker] Metrics telemetry server listening on port {METRICS_PORT}.')

    worker = Worker(
        client,
        task_queue=TEMPORAL_TASK_QUEUE,
        workflows=[BookingWorkflow],
        activities=[
            reserve_flight_activity,
            cancel_flight_activity,
            confirm_flight_activity,
            reserve_hotel_activity,
            cancel_hotel_activity,
            confirm_hotel_activity,
            charge_payment_activity,
            refund_payment_activity,
        ],
    )

    print(f'[Temporal Worker] Listening on task queue: "{TEMPORAL_TASK_QUEUE}"')
    print('[Temporal Worker] Registered Workflow: BookingWorkflow')
    print('[Temporal Worker] Registered Activities: Flight (3), Hotel (3), Payment (2)')
    print('[Temporal Worker] Ready to process bookings. Press Ctrl+C to exit.')

    await worker.run()


if __name__ == '__main__':
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        print('\n[Temporal Worker] Shutting down gracefully.')

"""
On-demand health check engine for microservices and Temporal engine.
"""

import os
import time
import httpx
from temporalio.client import Client
from models import ServiceHealth, SystemHealthReport


FLIGHT_SERVICE_URL = os.getenv('FLIGHT_SERVICE_URL', 'http://localhost:8001')
HOTEL_SERVICE_URL = os.getenv('HOTEL_SERVICE_URL', 'http://localhost:8002')
PAYMENT_SERVICE_URL = os.getenv('PAYMENT_SERVICE_URL', 'http://localhost:8003')
NAIVE_ORCHESTRATOR_URL = os.getenv('NAIVE_ORCHESTRATOR_URL', 'http://localhost:8004')
TEMPORAL_HOST = os.getenv('TEMPORAL_HOST', 'localhost:7233')


async def check_http_service(name: str, base_url: str) -> ServiceHealth:
    url = f'{base_url}/health'
    start_time = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.get(url)
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            if resp.status_code == 200:
                return ServiceHealth(name=name, url=base_url, status='UP', latency_ms=elapsed_ms)
            return ServiceHealth(
                name=name,
                url=base_url,
                status='DOWN',
                latency_ms=elapsed_ms,
                error=f'Status code {resp.status_code}',
            )
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return ServiceHealth(
            name=name,
            url=base_url,
            status='DOWN',
            latency_ms=elapsed_ms,
            error=str(exc),
        )


async def check_temporal_service() -> ServiceHealth:
    start_time = time.perf_counter()
    try:
        client = await Client.connect(TEMPORAL_HOST)
        # Check basic cluster info / ping
        await client.service_client.check_health()
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return ServiceHealth(
            name='Temporal Engine',
            url=f'grpc://{TEMPORAL_HOST}',
            status='UP',
            latency_ms=elapsed_ms,
        )
    except Exception as exc:
        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        return ServiceHealth(
            name='Temporal Engine',
            url=f'grpc://{TEMPORAL_HOST}',
            status='DOWN',
            latency_ms=elapsed_ms,
            error=str(exc),
        )


async def check_all_services() -> SystemHealthReport:
    """Executes on-demand health check across all distributed services."""
    flight_res = await check_http_service('Flight Service', FLIGHT_SERVICE_URL)
    hotel_res = await check_http_service('Hotel Service', HOTEL_SERVICE_URL)
    payment_res = await check_http_service('Payment Service', PAYMENT_SERVICE_URL)
    naive_res = await check_http_service('Naive Orchestrator', NAIVE_ORCHESTRATOR_URL)
    temporal_res = await check_temporal_service()

    services = [flight_res, hotel_res, payment_res, naive_res, temporal_res]
    is_healthy = all(s.status == 'UP' for s in services)

    return SystemHealthReport(
        overall_status='HEALTHY' if is_healthy else 'DEGRADED',
        services=services,
    )

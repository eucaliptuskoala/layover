"""
Layover API Gateway Application.
Provides unified HTTP ingress for client applications (CLI, Web UI),
exposing health telemetry, scenario metadata, and booking dispatch endpoints.
"""

import sys
from pathlib import Path
from typing import Any, Dict, List

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware

# Ensure gateway directory is on sys.path for direct module imports
GATEWAY_DIR = Path(__file__).resolve().parent
if str(GATEWAY_DIR) not in sys.path:
    sys.path.insert(0, str(GATEWAY_DIR))

try:
    from .dispatcher import dispatch_booking
    from .health import check_all_services
    from .models import (
        BookingRequest,
        BookingResponse,
        SystemHealthReport,
    )
    from .scenarios import DEFAULT_SCENARIOS
except ImportError:
    from dispatcher import dispatch_booking
    from health import check_all_services
    from models import (
        BookingRequest,
        BookingResponse,
        SystemHealthReport,
    )
    from scenarios import DEFAULT_SCENARIOS


app = FastAPI(
    title='Layover Gateway API',
    description='API Gateway and orchestrator dispatcher for distributed travel booking system.',
    version='1.0.0',
)


# -----------------------------------------------------------------------------
# CORS Configuration
# -----------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


# -----------------------------------------------------------------------------
# Root & Information Endpoints
# -----------------------------------------------------------------------------
@app.get(
    '/',
    summary='Gateway Index',
    tags=['General'],
)
async def get_index() -> Dict[str, str]:
    return {
        'service': 'Layover API Gateway',
        'status': 'OPERATIONAL',
        'version': '1.0.0',
        'docs_url': '/docs',
    }


# -----------------------------------------------------------------------------
# Health Telemetry Endpoints
# -----------------------------------------------------------------------------
@app.get(
    '/health',
    response_model=SystemHealthReport,
    summary='Overall System Health Telemetry',
    tags=['Telemetry'],
)
@app.get(
    '/api/health',
    response_model=SystemHealthReport,
    summary='Cluster Health Telemetry (API prefix)',
    tags=['Telemetry'],
)
async def get_system_health() -> SystemHealthReport:
    """
    Executes live on-demand health probes across all microservices
    (Flight, Hotel, Payment) and the Temporal orchestration cluster.
    """
    return await check_all_services()


# -----------------------------------------------------------------------------
# Scenarios Metadata Endpoint
# -----------------------------------------------------------------------------
@app.get(
    '/api/scenarios',
    summary='List Available Testing Scenarios',
    tags=['Scenarios'],
)
async def list_scenarios() -> List[Dict[str, Any]]:
    """
    Returns predefined scenarios available for experimental testing.
    Includes deterministic fault descriptions and default values.
    """
    result = []

    for scenario_enum, details in DEFAULT_SCENARIOS.items():
        result.append({
            'key': scenario_enum.value,
            'name': scenario_enum.value.replace('_', ' ').title(),
            'description': details.get('description', ''),
            'customer_id': details.get('customer_id'),
            'flight_number': details.get('flight_number'),
            'flight_price': details.get('flight_price'),
            'hotel_name': details.get('hotel_name'),
            'hotel_price': details.get('hotel_price'),
            'expected_total': round(details.get('flight_price', 0.0) + details.get('hotel_price', 0.0), 2),
        })

    return result


# -----------------------------------------------------------------------------
# Booking Dispatch Endpoint
# -----------------------------------------------------------------------------
@app.post(
    '/api/bookings',
    response_model=BookingResponse,
    status_code=status.HTTP_200_OK,
    summary='Dispatch Travel Booking Transaction',
    tags=['Bookings'],
)
async def create_booking(request: BookingRequest) -> BookingResponse:
    """
    Dispatches a unified travel booking request to the chosen orchestrator.
    Executes forward activities or coordinates LIFO compensation rollbacks.
    """
    return await dispatch_booking(request)


# -----------------------------------------------------------------------------
# CLI Entrypoint for Local Development
# -----------------------------------------------------------------------------
if __name__ == '__main__':
    import uvicorn

    uvicorn.run(
        'main:app',
        host='0.0.0.0',
        port=8000,
        reload=True,
    )

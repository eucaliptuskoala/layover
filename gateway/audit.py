"""
Distributed database state audit engine for Layover.
Queries microservices via HTTP to detect stranded/orphaned holds without violating database-per-service isolation.
"""

import asyncio
import os
from typing import Optional
import httpx

try:
    from .models import BookingAuditReport, ServiceAuditRecord
except ImportError:
    from models import BookingAuditReport, ServiceAuditRecord


FLIGHT_SERVICE_URL = os.getenv('FLIGHT_SERVICE_URL', 'http://localhost:8001').rstrip('/')
HOTEL_SERVICE_URL = os.getenv('HOTEL_SERVICE_URL', 'http://localhost:8002').rstrip('/')
PAYMENT_SERVICE_URL = os.getenv('PAYMENT_SERVICE_URL', 'http://localhost:8003').rstrip('/')


async def _inspect_service(
    client: httpx.AsyncClient,
    service_name: str,
    database_file: str,
    url: str,
    active_statuses: set[str],
) -> ServiceAuditRecord:
    """Queries an upstream microservice for booking status and identifies stranded records."""
    try:
        resp = await client.get(url, timeout=3.0)

        if resp.status_code == 200:
            data = resp.json()
            status = data.get('status', 'UNKNOWN')
            is_stranded = status in active_statuses
            msg = (
                f'Stranded hold active in {database_file}'
                if is_stranded
                else f'Consistent state ({status})'
            )
            return ServiceAuditRecord(
                service_name=service_name,
                database_file=database_file,
                status=status,
                details=data,
                is_stranded=is_stranded,
                message=msg,
            )

        if resp.status_code == 404:
            return ServiceAuditRecord(
                service_name=service_name,
                database_file=database_file,
                status='NOT_FOUND',
                details=None,
                is_stranded=False,
                message=f'No record found in {database_file}',
            )

        return ServiceAuditRecord(
            service_name=service_name,
            database_file=database_file,
            status=f'HTTP_{resp.status_code}',
            details=None,
            is_stranded=False,
            message=f'Service returned HTTP {resp.status_code}',
        )

    except Exception as exc:
        return ServiceAuditRecord(
            service_name=service_name,
            database_file=database_file,
            status='UNREACHABLE',
            details=None,
            is_stranded=False,
            message=f'Connection error: {exc}',
        )


async def audit_booking_state(
    booking_id: str,
    client: Optional[httpx.AsyncClient] = None,
) -> BookingAuditReport:
    """
    Audits the current state of booking_id across all independent microservice databases via HTTP.
    Identifies stranded holds (e.g. RESERVED holds that were never compensated due to coordinator crashes).
    """

    async def _run(c: httpx.AsyncClient) -> BookingAuditReport:
        flight_task = _inspect_service(
            c,
            'Flight Service',
            'flight.db',
            f'{FLIGHT_SERVICE_URL}/reservations/{booking_id}',
            {'RESERVED'},
        )
        hotel_task = _inspect_service(
            c,
            'Hotel Service',
            'hotel.db',
            f'{HOTEL_SERVICE_URL}/reservations/{booking_id}',
            {'RESERVED'},
        )
        payment_task = _inspect_service(
            c,
            'Payment Service',
            'payment.db',
            f'{PAYMENT_SERVICE_URL}/payments/{booking_id}',
            {'CHARGED'},
        )

        flight_audit, hotel_audit, payment_audit = await asyncio.gather(
            flight_task,
            hotel_task,
            payment_task,
        )

        has_stranded = (
            flight_audit.is_stranded or hotel_audit.is_stranded or payment_audit.is_stranded
        )

        stranded_services = []
        if flight_audit.is_stranded:
            stranded_services.append('flight.db (seat hold)')
        if hotel_audit.is_stranded:
            stranded_services.append('hotel.db (room hold)')
        if payment_audit.is_stranded:
            stranded_services.append('payment.db (captured funds)')

        if has_stranded:
            summary = f'Stranded records detected: {", ".join(stranded_services)}'
        else:
            summary = 'All service databases are in a consistent state.'

        return BookingAuditReport(
            booking_id=booking_id,
            has_stranded_records=has_stranded,
            flight=flight_audit,
            hotel=hotel_audit,
            payment=payment_audit,
            summary=summary,
        )

    if client is not None:
        return await _run(client)

    async with httpx.AsyncClient() as c:
        return await _run(c)

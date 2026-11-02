"""
Command-Line Interface for Layover travel booking system.
Communicates through the Gateway layer for on-demand health checks and scenario dispatching.
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure gateway layer is on import path
GATEWAY_DIR = Path(__file__).resolve().parent.parent / 'gateway'
if str(GATEWAY_DIR) not in sys.path:
    sys.path.insert(0, str(GATEWAY_DIR))

from dispatcher import dispatch_booking
from health import check_all_services
from models import BookingRequest, OrchestratorType, ScenarioType


def print_banner(title: str) -> None:
    print('\n' + '=' * 64)
    print(f'  {title}')
    print('=' * 64)


async def run_healthcheck() -> None:
    print_banner('System Health Inspection')
    print('Checking microservices and Temporal engine...\n')

    report = await check_all_services()

    for s in report.services:
        status_icon = '✓' if s.status == 'UP' else '✗'
        latency = f'({s.latency_ms} ms)' if s.latency_ms is not None else ''
        error_info = f' [Error: {s.error}]' if s.error else ''
        print(f'  [{status_icon}] {s.name:<24} — {s.status:<4} {latency:<10}{error_info}')

    print('-' * 64)
    print(f'  Overall System State: {report.overall_status}')
    print('=' * 64 + '\n')


async def run_booking(args: argparse.Namespace) -> None:
    orchestrator = OrchestratorType(args.orchestrator)
    scenario = ScenarioType(args.scenario)

    req = BookingRequest(
        orchestrator=orchestrator,
        scenario=scenario,
        booking_id=args.id,
        customer_id=args.customer,
        flight_number=args.flight,
        flight_price=args.flight_price,
        hotel_name=args.hotel,
        hotel_price=args.hotel_price,
    )

    print_banner(f'Dispatching Booking via {orchestrator.value.title()} Orchestrator')
    print(f'Scenario:      {scenario.value}')
    if args.id:
        print(f'Target ID:     {args.id}')
    print('Connecting to orchestrator and awaiting result...\n')

    resp = await dispatch_booking(req)

    print('-' * 64)
    print(f'Booking ID:    {resp.booking_id}')
    print(f'Total Amount:  ${resp.total_amount}')
    print(f'Final Status:  {resp.status}')

    if resp.steps_completed:
        print('\nForward Steps Completed:')
        for step in resp.steps_completed:
            print(f'  [✓] {step}')

    if resp.compensations_executed:
        print('\nCompensations Triggered (LIFO):')
        for comp in resp.compensations_executed:
            print(f'  [↺] {comp}')

    if resp.error_message:
        print(f'\nFailure Reason: {resp.error_message}')

    if resp.temporal_ui_url:
        print(f'\nTemporal Web UI: {resp.temporal_ui_url}')

    print('=' * 64 + '\n')


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Layover Travel Booking Command-Line Interface',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check system health
  uv run --directory clients python cli.py --health

  # Run Happy Path booking via Temporal
  uv run --directory clients python cli.py --scenario happy_path

  # Test Saga rollback on Payment failure (Insufficient Funds)
  uv run --directory clients python cli.py --scenario fail_payment

  # Test Saga rollback on Hotel conflict
  uv run --directory clients python cli.py --scenario fail_hotel

  # Custom booking parameters
  uv run --directory clients python cli.py --customer user_1 --flight-price 400 --hotel-price 250

  # Or from within the clients directory:
  cd clients && uv run python cli.py --health
        """,
    )

    parser.add_argument(
        '-H', '--health',
        action='store_true',
        help='Run on-demand healthcheck across microservices and Temporal engine',
    )
    parser.add_argument(
        '-s', '--scenario',
        choices=['happy_path', 'fail_hotel', 'fail_payment', 'custom'],
        default='happy_path',
        help='Predefined scenario to execute (default: happy_path)',
    )
    parser.add_argument(
        '-o', '--orchestrator',
        choices=['temporal', 'naive'],
        default='temporal',
        help='Orchestration coordinator to invoke (default: temporal)',
    )
    parser.add_argument('--id', help='Explicit booking correlation ID')
    parser.add_argument('--customer', help='Customer ID (e.g. user_1)')
    parser.add_argument('--flight', help='Flight number (e.g. LH-204)')
    parser.add_argument('--flight-price', type=float, help='Flight seat price')
    parser.add_argument('--hotel', help='Hotel name')
    parser.add_argument('--hotel-price', type=float, help='Hotel room price')

    args = parser.parse_args()

    if args.health:
        asyncio.run(run_healthcheck())
    else:
        asyncio.run(run_booking(args))


if __name__ == '__main__':
    main()

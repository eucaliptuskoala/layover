#!/usr/bin/env python3
'''
Layover Database Integrity & Zombie Record Detection Script.

Inspects SQLite databases across Flight, Hotel, and Payment microservice
Docker containers to verify distributed transaction consistency and detect
orphaned holds left by process crashes.
'''

import argparse
import json
import subprocess
import sys
from typing import Any, Dict, List, Optional


def query_container_sqlite(container: str, query: str) -> List[Dict[str, Any]]:
    '''
    Executes a read-only query inside a Docker container using python3/sqlite3
    and returns parsed JSON records.
    '''
    inline_cmd = (
        'import sqlite3, json; '
        'con = sqlite3.connect(\'/app/data/' + container.replace('layover-', '') + '.db\'); '
        'con.row_factory = sqlite3.Row; '
        'rows = [dict(r) for r in con.execute(\"' + query + '\")]; '
        'print(json.dumps(rows))'
    )

    try:
        result = subprocess.run(
            ['docker', 'exec', container, 'python3', '-c', inline_cmd],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout.strip() or '[]')
    except subprocess.CalledProcessError as exc:
        print(f'[ERROR] Could not query container {container}: {exc.stderr.strip()}', file=sys.stderr)
        return []
    except Exception as exc:
        print(f'[ERROR] Unexpected failure querying {container}: {exc}', file=sys.stderr)
        return []


def get_accounts() -> List[Dict[str, Any]]:
    '''Retrieves customer balances from layover-payment.'''
    inline_cmd = (
        'import sqlite3, json; '
        'con = sqlite3.connect(\'/app/data/payment.db\'); '
        'con.row_factory = sqlite3.Row; '
        'rows = [dict(r) for r in con.execute(\"SELECT customer_id, balance FROM accounts\")]; '
        'print(json.dumps(rows))'
    )
    try:
        result = subprocess.run(
            ['docker', 'exec', 'layover-payment', 'python3', '-c', inline_cmd],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout.strip() or '[]')
    except Exception:
        return []


def set_account_balance(amount: float, customer_id: str = 'user_1') -> bool:
    '''Updates customer balance in layover-payment.'''
    inline_cmd = (
        'import sqlite3; '
        'con = sqlite3.connect(\'/app/data/payment.db\'); '
        f'con.execute(\"UPDATE accounts SET balance = {amount} WHERE customer_id = \'{customer_id}\'\"); '
        'con.commit()'
    )
    try:
        subprocess.run(
            ['docker', 'exec', 'layover-payment', 'python3', '-c', inline_cmd],
            check=True,
            capture_output=True,
        )
        return True
    except Exception as exc:
        print(f'[ERROR] Could not update balance: {exc}', file=sys.stderr)
        return False


def evaluate_booking(
    flight: Optional[Dict[str, Any]],
    hotel: Optional[Dict[str, Any]],
    payment: Optional[Dict[str, Any]],
) -> str:
    '''
    Evaluates cross-database transaction consistency.
    Returns: CONSISTENT_SUCCESS, CONSISTENT_ROLLBACK, ORPHANED_HOLD, or INCONSISTENT.
    '''
    f_status = flight.get('status') if flight else 'NONE'
    h_status = hotel.get('status') if hotel else 'NONE'
    p_status = payment.get('status') if payment else 'NONE'

    # Happy path: all confirmed and paid
    if f_status == 'CONFIRMED' and h_status == 'CONFIRMED' and p_status == 'CHARGED':
        return 'CONSISTENT_SUCCESS'

    # Clean rollback: compensations completed
    if f_status == 'CANCELLED':
        if h_status in ('CANCELLED', 'NONE') and p_status in ('REFUNDED', 'NONE'):
            return 'CONSISTENT_ROLLBACK'

    # Orphaned hold: flight or hotel stuck in RESERVED while others are missing/failed
    if f_status == 'RESERVED':
        return 'ORPHANED_HOLD (FLIGHT LEAK)'

    if h_status == 'RESERVED':
        return 'ORPHANED_HOLD (HOTEL LEAK)'

    return 'INCONSISTENT'


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Check distributed database consistency and detect zombie records across Layover microservices.',
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=8,
        help='Maximum number of recent records to inspect per service (default: 8)',
    )
    parser.add_argument(
        '--set-balance',
        type=float,
        default=None,
        help='Set customer user_1 balance to specified amount (e.g. 1000.0)',
    )
    args = parser.parse_args()

    if args.set_balance is not None:
        set_account_balance(args.set_balance)

    limit = args.limit

    print('=' * 88)
    print(' LAYOVER DISTRIBUTED DATABASE INTEGRITY AUDIT')
    print(' Inspecting SQLite databases across independent microservice containers')
    print('=' * 88)

    # 1. Fetch raw records
    flights = query_container_sqlite(
        'layover-flight',
        f'SELECT booking_id, flight_number, price, status, created_at FROM flight_bookings ORDER BY id DESC LIMIT {limit}',
    )
    hotels = query_container_sqlite(
        'layover-hotel',
        f'SELECT booking_id, hotel_name, price, status, created_at FROM hotel_bookings ORDER BY id DESC LIMIT {limit}',
    )
    payments = query_container_sqlite(
        'layover-payment',
        f'SELECT booking_id, amount, status, created_at FROM payments ORDER BY id DESC LIMIT {limit}',
    )
    accounts = get_accounts()

    # 2. Build index by booking_id
    flight_map = {r['booking_id']: r for r in flights}
    hotel_map = {r['booking_id']: r for r in hotels}
    payment_map = {r['booking_id']: r for r in payments}

    # Ordered unique booking IDs preserving recent ordering
    all_booking_ids: List[str] = []
    for r in flights + hotels + payments:
        bid = r.get('booking_id')
        if bid and bid not in all_booking_ids:
            all_booking_ids.append(bid)

    # Limit total inspected
    all_booking_ids = all_booking_ids[:limit]

    # 3. Print Customer Account Balances
    print('\n[1] CUSTOMER BALANCES (Payment Service DB):')
    if accounts:
        for acc in accounts:
            print(f'  - Customer: {acc["customer_id"]}  |  Balance: ${acc["balance"]:,.2f}')
    else:
        print('  - No account records found.')

    # 4. Print Booking Audit Table
    print('\n[2] TRANSACTION AUDIT & ZOMBIE DETECTION TABLE:')
    header_fmt = '{:<18} | {:<12} | {:<12} | {:<10} | {:<28}'
    row_fmt = '{:<18} | {:<12} | {:<12} | {:<10} | {:<28}'

    print('-' * 88)
    print(header_fmt.format('Booking ID', 'Flight DB', 'Hotel DB', 'Payment DB', 'Integrity Verdict'))
    print('-' * 88)

    orphaned_count = 0
    consistent_count = 0

    if not all_booking_ids:
        print('  No booking transactions found in databases.')
    else:
        for bid in all_booking_ids:
            f = flight_map.get(bid)
            h = hotel_map.get(bid)
            p = payment_map.get(bid)

            f_str = f['status'] if f else '-'
            h_str = h['status'] if h else '-'
            p_str = p['status'] if p else '-'

            verdict = evaluate_booking(f, h, p)

            if 'ORPHANED' in verdict or 'INCONSISTENT' in verdict:
                orphaned_count += 1
                badge = f'[!] {verdict}'
            elif verdict == 'CONSISTENT_SUCCESS':
                consistent_count += 1
                badge = '[OK] CONFIRMED'
            else:
                consistent_count += 1
                badge = '[OK] COMPENSATED'

            # Abbreviate long booking IDs for clean terminal table display
            short_bid = bid if len(bid) <= 18 else bid[:15] + '...'
            print(row_fmt.format(short_bid, f_str, h_str, p_str, badge))

    print('-' * 88)

    # 5. Summary & Evaluation
    print('\n[3] AUDIT SUMMARY:')
    print(f'  - Total Transactions Inspected: {len(all_booking_ids)}')
    print(f'  - Consistent (Confirmed or Rolled back): {consistent_count}')
    print(f'  - Orphaned Holds / Inconsistent States: {orphaned_count}')

    if orphaned_count > 0:
        print('\n[ATTENTION: DEMO EVIDENCE READY]')
        print('  One or more ORPHANED HOLDS detected above.')
        print('  This empirically proves process crash vulnerability in the Naive Orchestrator:')
        print('  A flight seat or hotel room remained RESERVED because the in-memory rollback stack')
        print('  died with the process before compensation could be dispatched.')
    else:
        print('\n[ALL RECORDED TRANSACTIONS CONSISTENT]')
        print('  Every transaction either fully completed or cleanly compensated.')

    print('=' * 88 + '\n')


if __name__ == '__main__':
    main()

"""
Payment Service Database Layer.
Manages customer account balances and atomic charge/refund operations via aiosqlite.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import uuid
import aiosqlite
from models import PaymentStatus


DEFAULT_DB_PATH = str(Path(__file__).resolve().parent / 'payment.db')

CREATE_ACCOUNTS_TABLE_SQL = '''
CREATE TABLE IF NOT EXISTS accounts (
    customer_id TEXT PRIMARY KEY,
    balance REAL NOT NULL
);
'''

CREATE_PAYMENTS_TABLE_SQL = '''
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payment_id TEXT UNIQUE NOT NULL,
    booking_id TEXT UNIQUE NOT NULL,
    customer_id TEXT NOT NULL,
    amount REAL NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(customer_id) REFERENCES accounts(customer_id)
);
'''


class PaymentDatabase:
    """Manages SQLite operations for accounts and payments."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path

    async def init_db(self) -> None:
        """Initializes tables and seeds default demo accounts."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(CREATE_ACCOUNTS_TABLE_SQL)
            await db.execute(CREATE_PAYMENTS_TABLE_SQL)
            # Seed demo user 'user_1' with 1000.0 balance if not exists
            await db.execute(
                '''
                INSERT OR IGNORE INTO accounts (customer_id, balance)
                VALUES ('user_1', 1000.0)
                '''
            )
            await db.commit()

    async def get_account(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves customer account details."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            async with db.execute(
                'SELECT customer_id, balance FROM accounts WHERE customer_id = ?',
                (customer_id,),
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def create_or_update_account(
        self,
        customer_id: str,
        balance: float,
    ) -> Dict[str, Any]:
        """Creates or resets an account balance."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            await db.execute(
                '''
                INSERT INTO accounts (customer_id, balance)
                VALUES (?, ?)
                ON CONFLICT(customer_id) DO UPDATE SET balance = excluded.balance
                ''',
                (customer_id, balance),
            )
            await db.commit()

            return {'customer_id': customer_id, 'balance': balance}

    async def charge(
        self,
        booking_id: str,
        customer_id: str,
        amount: float,
    ) -> Dict[str, Any]:
        """Atomically checks balance, deducts amount, and records CHARGED payment."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # 1. Check account balance
            async with db.execute(
                'SELECT balance FROM accounts WHERE customer_id = ?',
                (customer_id,),
            ) as cursor:
                account_row = await cursor.fetchone()
                if not account_row:
                    raise ValueError(f'Account not found for customer: {customer_id}')

                current_balance = account_row['balance']
                if current_balance < amount:
                    raise ValueError(
                        f'Insufficient funds: available {current_balance}, required {amount}'
                    )

            # 2. Deduct balance
            await db.execute(
                'UPDATE accounts SET balance = balance - ? WHERE customer_id = ?',
                (amount, customer_id),
            )

            # 3. Insert payment record
            payment_id = f'pay-{uuid.uuid4().hex[:8]}'
            cursor = await db.execute(
                '''
                INSERT INTO payments (payment_id, booking_id, customer_id, amount, status)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (payment_id, booking_id, customer_id, amount, PaymentStatus.CHARGED.value),
            )
            await db.commit()

            inserted_id = cursor.lastrowid
            async with db.execute(
                'SELECT id, payment_id, booking_id, customer_id, amount, status, created_at FROM payments WHERE id = ?',
                (inserted_id,),
            ) as select_cursor:
                row = await select_cursor.fetchone()
                return dict(row) if row else {}

    async def refund(self, booking_id: str) -> Dict[str, Any]:
        """Atomically restores customer balance and updates payment status to REFUNDED."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            # 1. Fetch payment
            async with db.execute(
                'SELECT id, payment_id, booking_id, customer_id, amount, status FROM payments WHERE booking_id = ?',
                (booking_id,),
            ) as cursor:
                payment_row = await cursor.fetchone()
                if not payment_row:
                    raise ValueError(f'Payment not found for booking_id: {booking_id}')

                if payment_row['status'] == PaymentStatus.REFUNDED.value:
                    raise ValueError(f'Payment for {booking_id} has already been refunded')

                customer_id = payment_row['customer_id']
                amount = payment_row['amount']

            # 2. Restore balance
            await db.execute(
                'UPDATE accounts SET balance = balance + ? WHERE customer_id = ?',
                (amount, customer_id),
            )

            # 3. Update payment status to REFUNDED
            await db.execute(
                'UPDATE payments SET status = ? WHERE booking_id = ?',
                (PaymentStatus.REFUNDED.value, booking_id),
            )
            await db.commit()

            async with db.execute(
                'SELECT id, payment_id, booking_id, customer_id, amount, status, created_at FROM payments WHERE booking_id = ?',
                (booking_id,),
            ) as select_cursor:
                row = await select_cursor.fetchone()
                return dict(row) if row else {}

    async def get_payment(self, booking_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves payment details by booking_id."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            async with db.execute(
                'SELECT id, payment_id, booking_id, customer_id, amount, status, created_at FROM payments WHERE booking_id = ?',
                (booking_id,),
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def list_payments(self) -> List[Dict[str, Any]]:
        """Returns all payment transactions."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            async with db.execute(
                'SELECT id, payment_id, booking_id, customer_id, amount, status, created_at FROM payments ORDER BY id DESC'
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]


db_instance = PaymentDatabase()

"""
Flight Service Database Layer.
Manages SQLite persistence for flight reservations via aiosqlite.
"""

from pathlib import Path
from typing import Any, Dict, List, Optional
import aiosqlite
from models import FlightBookingStatus


DEFAULT_DB_PATH = str(Path(__file__).resolve().parent / 'flight.db')

CREATE_FLIGHT_TABLE_SQL = '''
CREATE TABLE IF NOT EXISTS flight_bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    booking_id TEXT UNIQUE NOT NULL,
    customer_id TEXT NOT NULL,
    flight_number TEXT NOT NULL,
    price REAL NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
'''


class FlightDatabase:
    """Manages SQLite operations for flight reservations."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path

    async def init_db(self) -> None:
        """Initializes the database schema."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(CREATE_FLIGHT_TABLE_SQL)
            await db.commit()

    async def create_reservation(
        self,
        booking_id: str,
        customer_id: str,
        flight_number: str,
        price: float,
        status: FlightBookingStatus = FlightBookingStatus.RESERVED,
    ) -> Dict[str, Any]:
        """Creates a new flight reservation."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            cursor = await db.execute(
                '''
                INSERT INTO flight_bookings (booking_id, customer_id, flight_number, price, status)
                VALUES (?, ?, ?, ?, ?)
                ''',
                (booking_id, customer_id, flight_number, price, status.value),
            )
            await db.commit()

            inserted_id = cursor.lastrowid
            async with db.execute(
                'SELECT id, booking_id, customer_id, flight_number, price, status, created_at FROM flight_bookings WHERE id = ?',
                (inserted_id,),
            ) as select_cursor:
                row = await select_cursor.fetchone()
                return dict(row) if row else {}

    async def get_reservation(self, booking_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves a reservation by booking_id."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            async with db.execute(
                'SELECT id, booking_id, customer_id, flight_number, price, status, created_at FROM flight_bookings WHERE booking_id = ?',
                (booking_id,),
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    async def update_status(
        self,
        booking_id: str,
        status: FlightBookingStatus,
    ) -> Optional[Dict[str, Any]]:
        """Updates the status of an existing reservation."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            await db.execute(
                'UPDATE flight_bookings SET status = ? WHERE booking_id = ?',
                (status.value, booking_id),
            )
            await db.commit()

            return await self.get_reservation(booking_id)

    async def update_status_atomic(
        self,
        booking_id: str,
        from_status: FlightBookingStatus,
        to_status: FlightBookingStatus,
    ) -> bool:
        """Atomically transitions status from from_status to to_status (Compare-and-Swap)."""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                '''
                UPDATE flight_bookings
                SET status = ?
                WHERE booking_id = ? AND status = ?
                ''',
                (to_status.value, booking_id, from_status.value),
            )
            await db.commit()
            return cursor.rowcount > 0

    async def list_reservations(self) -> List[Dict[str, Any]]:
        """Returns all flight reservations."""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            async with db.execute(
                'SELECT id, booking_id, customer_id, flight_number, price, status, created_at FROM flight_bookings ORDER BY id DESC'
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]


db_instance = FlightDatabase()

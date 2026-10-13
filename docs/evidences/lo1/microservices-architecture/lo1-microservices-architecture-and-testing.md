# Microservices Architecture, Database Isolation & Contract Testing

## Introduction

> Built three autonomous FastAPI microservices (Flight, Hotel, Payment) with isolated SQLite databases and a 3-tier architecture, establishing idempotent forward and compensating REST contracts validated by 32 automated unit and integration tests.

---

## Context and the Problem

In the Layover project, I am researching how distributed systems handle partial failures during multi-step transactions (like booking a flight, reserving a hotel room, and processing payment).

In a traditional monolithic backend with a single database, this is straightforward: all three updates happen inside a single database transaction (`BEGIN ... COMMIT`). If the payment fails or the server loses power, the database engine simply executes a `ROLLBACK`, leaving no partial records behind.

In a microservices architecture, each service owns its own database. There is no distributed database engine that can automatically roll back across independent network services.

If a customer tries to book a trip, the flight might be reserved and the hotel room held, but if the payment call times out or fails due to insufficient balance, the system enters an inconsistent state. Without explicit forward actions (`/reserve`, `/charge`) and reliable compensating actions (`/cancel`, `/refund`), hotels and airlines hold inventory indefinitely, and customers risk getting charged for cancelled trips.

Before I could introduce any workflow coordinator (like a sequential script or a workflow engine like Temporal), I needed to build the three underlying services and prove that their API contracts and state machines could reliably handle both forward reservations and rollback compensations.

---

## Systems Thinking: How It Fits the Project

I designed these three services strictly around the **Database-per-Service** architectural pattern:

* **Flight Service (`services/flight/`):** Manages seat reservations and status transitions in `flight.db`.
* **Hotel Service (`services/hotel/`):** Manages room bookings and status transitions in `hotel.db`.
* **Payment Service (`services/payment/`):** Manages customer balances and transactions in `payment.db`.

No service has direct database access to another service's tables. Communication happens exclusively over HTTP REST contracts.

```
+--------------------------------------------------------------------------+
|                 Orchestrator Layer (Cycles 3 & 4)                        |
|        (Sequential Try/Catch Baseline  OR  Temporal Saga Workflow)       |
+--------------------------------------------------------------------------+
       |                                |                               |
       | POST /reserve                  | POST /reserve                 | POST /charge
       | POST /cancel                   | POST /cancel                  | POST /refund
       v                                v                               v
+------------------+           +------------------+           +--------------------+
|  Flight Service  |           |  Hotel Service   |           |  Payment Service   |
| (services/flight)|           | (services/hotel) |           |(services/payment)  |
+------------------+           +------------------+           +--------------------+
       |                                |                               |
       v (Isolated)                     v (Isolated)                    v (Isolated)
+------------------+           +------------------+           +--------------------+
|    flight.db     |           |     hotel.db     |           |     payment.db     |
+------------------+           +------------------+           +--------------------+
```

To bind these services together without coupling their code, I established a clear data contract:

* **Global Correlation ID (`booking_id`):** Every booking flow generates a unique `booking_id` (e.g., `bk-100`). This ID is passed to all three services so every reservation and payment shares the same identifier across logs and databases.
* **Symmetric Forward and Compensating Endpoints:** Every forward action that modifies state has an exact undo action:
  * Flight: `POST /reserve` $\leftrightarrow$ `POST /cancel`
  * Hotel: `POST /reserve` $\leftrightarrow$ `POST /cancel`
  * Payment: `POST /charge` $\leftrightarrow$ `POST /refund`

This clean separation ensures that the upcoming coordinators in Cycle 3 (Temporal) and Cycle 4 (Naive baseline) interact with the exact same API contracts.

---

## Progressive Engineering Steps

I developed the services and their validation harness across four distinct steps:

### 1 Microservice Directory & Environment Isolation

Instead of keeping all three services in a single monolithic Python project with shared dependencies, I separated each service into its own folder with its own `pyproject.toml` and virtual environment managed by `uv`.

```
services/
├── flight/   # pyproject.toml, .venv, main.py, service.py, database.py, tests/
├── hotel/    # pyproject.toml, .venv, main.py, service.py, database.py, tests/
└── payment/  # pyproject.toml, .venv, main.py, service.py, database.py, tests/
```

This guaranteed that dependencies remain isolated, simulating real independent services that can be updated, tested, and containerized on their own.

### 2 Compare-and-Swap (CAS) Atomic State Storage

Initially, state transitions could be checked in Python before updating the database:
`SELECT status` $\rightarrow$ `if status == 'RESERVED': UPDATE ...`

However, this creates a classic Time-of-Check to Time-of-Use (TOCTOU) race condition. If two network requests (such as a timeout retry and an intentional cancellation) hit the service at the same millisecond, both could read `RESERVED` and overwrite each other (Lost Update anomaly).

I replaced Python-level checks with atomic SQL Compare-and-Swap queries in `database.py`:

```sql
UPDATE flight_bookings 
SET status = ? 
WHERE booking_id = ? AND status = ?;
```

If the database modifies 1 row, the transition is atomic and valid. If it modifies 0 rows, the state has already moved, allowing the service to inspect the record and return an idempotent response or a conflict.

### 3 Layered 3-Tier Architecture (`Router -> Service -> Database`)

Putting all request validation, database queries, and business logic into route handlers leads to "Fat Controllers", which makes code difficult to test in isolation and maintain.

I refactored each service into three distinct layers:

1. **Controller (`main.py`):** Responsible solely for HTTP transport, JSON serialization via Pydantic, and mapping domain exceptions to HTTP status codes (`201 Created`, `200 OK`, `400 Bad Request`, `404 Not Found`, `409 Conflict`).
2. **Service Layer (`service.py`):** Holds pure business rules, validates state transitions, and enforces idempotency rules.
3. **Persistence Layer (`database.py`):** Encapsulates SQL queries and connection handling using `aiosqlite`.

To prevent databases from cluttering the root folder when services are launched from different directories, I anchored database paths using `Path(__file__).resolve().parent / '<service>.db'`.

### 4 Automated Testing Harness (32 Tests)

To prove that the services behave correctly before connecting them to an orchestrator, I wrote a comprehensive suite of unit and integration tests using `pytest`, `pytest-asyncio`, and `httpx.AsyncClient`.

The tests cover:

* Basic health checks (`/health`).
* Happy path forward bookings (`/reserve`, `/charge`).
* Account balance deductions and atomic guards rejecting insufficient funds (`400 Bad Request`).
* Compensating rollbacks (`/cancel`, `/refund`).
* Duplicate calls verifying that retried cancellations and refunds do not crash or double-refund money.
* Conflict guards returning `409 Conflict` if someone attempts to confirm an already cancelled reservation.

Every test uses an isolated temporary database (`tmp_path`) so test runs are completely repeatable and never leave leftover files behind.

---

## Key Decisions and What I Validated

### Embedded SQLite Files vs. Shared PostgreSQL

I deliberately chose embedded SQLite (`aiosqlite`) over running a PostgreSQL server for each service.

A common anti-pattern in student projects is running one shared PostgreSQL instance and creating three schemas. That creates a "distributed monolith" where services can secretly query each other's tables. Running three separate PostgreSQL containers would consume over 1.5 GB of RAM for a minimal research benchmark.

By using SQLite with `Path(__file__).parent`, each service owns its own physical file (`flight.db`, `hotel.db`, `payment.db`). It guarantees complete physical isolation while running instantly on local machines without complex Docker network setups during initial development.

### Idempotency and Safe Retries for Compensating Actions

In distributed workflows, network timeouts are inevitable. When an orchestrator experiences a timeout while calling `/cancel` or `/refund`, its standard behavior is to retry the request.

If a cancellation endpoint is not idempotent, a second call might return `400 Bad Request: Already Cancelled`, leading the orchestrator to assume the compensation failed.

I implemented idempotency guards in `service.py`:

* Calling `/cancel` on an already cancelled booking returns `200 OK` with the existing record.
* Calling `/refund` on an already refunded payment returns `200 OK` and does **not** credit the customer's balance a second time.

### Atomic Balance Protection in Payment Service

In the Payment service, handling money requires strict consistency.

I designed the `/charge` operation to check available funds and subtract the amount inside an atomic SQLite transaction. If an account has $1000 and two concurrent requests attempt to charge $600 each, the second request is rejected with `400 Insufficient funds`, preventing the account from going into a negative balance.

---

## From Proof of Concept to Next Cycle (Cycle 3: Temporal Saga)

With Cycle 2 complete, all three microservices are implemented, decoupled, and verified by 32 passing automated tests:

```bash
(cd services/flight && uv run pytest -v)   # 10 passed
(cd services/hotel && uv run pytest -v)    # 10 passed
(cd services/payment && uv run pytest -v)  # 12 passed
```

This provides the exact foundation required for **Cycle 3 (Temporal Workflow & Compensation)**. Because the REST contracts and compensating actions are fully verified and idempotent, I can now focus entirely on implementing the Temporal Saga orchestrator without worrying whether the microservices themselves are dropping data or crashing on retries.

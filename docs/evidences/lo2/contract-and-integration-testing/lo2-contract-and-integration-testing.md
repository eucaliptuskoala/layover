# Contract and Integration Testing (Automated Quality Harness)

## Introduction

> Designed and executed an automated testing harness of 32 unit and integration tests across three microservices, validating distributed state transitions, atomic Compare-and-Swap updates, idempotent compensations, and conflict guards using pytest and httpx.

---

## Context and the Problem

When developing distributed systems that manage money and reservations, manual endpoint testing (e.g. testing queries in Postman) is insufficient to guarantee reliability.

Distributed transactions suffer from partial failures that only appear during edge cases:

* What happens when an orchestrator sends a cancellation request twice because of a network retry?
* Does the payment service reject a transaction if a user has insufficient balance, or does the balance go negative?
* Can a customer resurrect an already cancelled flight by calling confirmation after a rollback?
* Does a database query silently overwrite a concurrent update when two requests hit the service at the same millisecond?

To answer these questions and satisfy **Software Quality (LO2)** requirements, I needed a reproducible, automated testing suite that validates every contract, database transition, and error condition on every code change without requiring manual intervention.

---

## Systems Thinking: How It Fits the Project

I structured the testing harness across two distinct testing boundaries to mirror our layered microservice architecture:

> [Attach: Architecture diagram illustrating the two-tier testing strategy: Unit tests verifying SQLite operations and CAS transitions, and Integration tests verifying HTTP endpoints via httpx.AsyncClient]

* **Unit Testing Boundary (`database.py`):** Tests raw SQLite operations, verifying that atomic queries and constraints execute correctly against the local database engine without network or HTTP overhead.
* **Integration Testing Boundary (`main.py` & `service.py`):** Tests the public REST contract, ensuring that incoming JSON requests trigger business rules, enforce idempotency, and return exact HTTP status codes.

---

## Progressive Engineering Steps

I built the testing harness across four progressive steps:

### 1 Establishing Strict Data Contracts & Status Enums

Before writing tests, I defined explicit data schemas and finite-state enums in `models.py` for each service:

* **Booking State Machine:** `RESERVED` $\rightarrow$ `CONFIRMED` or `CANCELLED`.
* **Payment State Machine:** `CHARGED` $\rightarrow$ `REFUNDED` (or `FAILED`).

Using Pydantic models with field constraints (`price > 0`, `amount > 0`), any request with negative amounts or missing IDs is rejected automatically at the HTTP boundary with `422 Unprocessable Entity`.

### 2 Database Layer Unit Testing

I wrote unit test suites (`test_flight_db.py`, `test_hotel_db.py`, `test_payment_db.py`) testing database operations directly.

Using a pytest fixture with `tmp_path`, each test receives its own isolated database file:

* Verifies table initialization (`init_db()`).
* Verifies initial account seeding (e.g., demo customer `'user_1'` starts with `$1000.0`).
* Verifies atomic balance deductions and asserts that attempting to charge more than the balance raises an immediate `ValueError('Insufficient funds')`.

### 3 Asynchronous API Integration Testing with ASGI Transport

To test HTTP endpoints without spawning live network servers and managing port conflicts, I used `httpx.AsyncClient` with `httpx.ASGITransport`.

> [Attach: Code snippet from conftest.py or test_flight_api.py showing the asynchronous client fixture configured with httpx.ASGITransport]

This executes requests directly through FastAPI's ASGI interface in-memory. Requests run at memory speed (sub-millisecond latency) while exercising the full HTTP stack: routing, dependency injection, Pydantic parsing, service domain logic, and SQLite persistence.

### 4 Testing Distributed Edge Cases and Idempotency

The most critical part of testing distributed transactions is proving that the system behaves correctly under failure and retry conditions:

* **Compensating Action Idempotency:**
  I wrote tests that call `/cancel` (or `/refund`) twice consecutively for the same `booking_id`. The test asserts that the second call returns `200 OK` with status `CANCELLED` (or `REFUNDED`), proving that network retries in an orchestrator will not fail.
* **Double-Refund Balance Guard:**
  In `test_payment_api.py`, the test charges $400 (balance drops to $600), calls `/refund` (balance returns to $1000), and calls `/refund` a second time. The test asserts that the balance remains exactly $1000 and is not credited twice.
* **Illegal State Transition Guard:**
  In `test_flight_api.py`, the test reserves a flight, cancels it, and then attempts to call `/confirm`. The test asserts that the server rejects the confirmation with `409 Conflict`, preventing zombie reservations.
* **Insufficient Funds Guard:**
  The test attempts to charge $1500 from an account with $1000. It asserts that the server returns `400 Bad Request` and that the account balance remains untouched at $1000.

---

## Key Decisions and What I Validated

### Isolated Temporary SQLite Databases vs. Mocking

A common approach in unit testing is mocking the database (e.g. `unittest.mock.patch`). However, mocking only proves that your code calls the mock; it does not prove that your SQL syntax is valid or that database constraints work.

I decided to use pytest's `tmp_path` fixture to spin up a real SQLite database file on disk for each test run. Because SQLite is lightweight and embedded, creating and destroying a real database takes less than 5 milliseconds. This gave us 100% confidence that real SQLite tables, `UNIQUE` constraints, and Compare-and-Swap queries behave correctly under real database locking.

### Validating Safe Retries (Idempotency Assertions)

In distributed Saga workflows, orchestrator retries must be safe.

I validated this property by writing explicit assertions checking both the response status code and the database state after duplicate calls.

> [Attach: Code snippet from test_payment_api.py showing assertions that verify duplicate /refund requests return 200 OK and maintain the exact balance without double crediting]

### Semantic HTTP Status Codes for Domain Errors

Rather than returning generic `500 Internal Server Error` responses when business rules fail, I mapped domain exceptions to standard HTTP status codes:

* Missing resource $\rightarrow$ `404 Not Found`
* Business logic rule violation (insufficient funds) $\rightarrow$ `400 Bad Request`
* State machine conflict (cancelling confirmed booking) $\rightarrow$ `409 Conflict`

This makes client error handling and orchestrator decision-making clean and predictable.

---

## From Proof of Concept to Next Cycle (Cycle 3: Temporal Saga)

The automated testing harness currently runs **32 tests** across the three microservices.

> [Attach: Screenshot of terminal running pytest across all three services showing all 32 tests passing green]

All 32 tests pass in under 1 second.

With this testing foundation in place, I have verified that every service contract is solid, idempotent, and protected against race conditions. This directly enables **Cycle 3 (Temporal Saga Orchestrator)**, where I can write workflow integration tests knowing that any unexpected failure originates from workflow coordination, not from faulty underlying service endpoints.

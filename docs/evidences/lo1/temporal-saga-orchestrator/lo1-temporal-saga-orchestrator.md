# Temporal Saga Orchestration & Distributed Compensations

## Introduction

> Designed and implemented a durable travel booking orchestrator using the Saga Pattern and Temporal Python SDK, featuring automated LIFO compensation rollbacks, decoupled Gateway mediation, and an in-memory time-skipping integration test harness.

---

## Context and the Problem

In a distributed microservice architecture with true database-per-service isolation, multi-service workflows (such as booking a flight, reserving a hotel, and charging a customer's payment card) cannot rely on ACID database transactions.

If any service encounters a failure mid-transaction (such as an overbooked hotel or insufficient funds on the payment step), naive implementations leave the system in an inconsistent "zombie" state:

* Flights remain reserved indefinitely without payment.
* Hotel inventory is blocked, preventing other customers from booking.
* Customers risk being billed for failed bookings if errors occur during subsequent steps.

To solve this problem for **Software Engineering (LO1)** and **Software Quality (LO2)**, I needed a durable workflow engine that guarantees eventual consistency across microservices through the **Saga Pattern**: executing forward steps sequentially and automatically triggering compensating actions in reverse order whenever partial failures strike.

---

## Systems Thinking: How It Fits the Project

I structured the orchestration layer around the **Ports & Adapters (Hexagonal)** architectural pattern:

> [Attach: Architecture diagram showing the 3-tier decoupling: Clients (CLI / React Web UI) -> Gateway Mediation Layer -> Temporal Saga Orchestrator -> Microservices (Flight, Hotel, Payment)]

* **Consumer Layer (`clients/`):** Thin interface adapters (the `cli.py` tool today, and the React/Vite dashboard in Cycle 4). They are decoupled from workflow execution internals.
* **Mediation Layer (`gateway/`):** The Application Service layer defining unified contracts (`BookingRequest`, `BookingResponse`), pre-flight healthcheck engines, and predefined scenario profiles (`happy_path`, `fail_hotel`, `fail_payment`).
* **Durable Orchestration Layer (`orchestrators/temporal/`):** The core Saga coordinator executing deterministic workflows and activities backed by Temporal's event-sourcing engine.
* **Microservices Layer (`services/`):** Autonomous REST microservices exposing symmetric forward actions (`/reserve`, `/charge`) and compensating actions (`/cancel`, `/refund`).

This separation ensures that in Cycle 4, when I build the Naive Sequential Coordinator and the React frontend, neither the microservices nor the clients need to be rewritten: both coordinators implement the exact same Gateway contract.

---

## Progressive Engineering Steps

I implemented and verified the Saga orchestrator across four progressive iterations:

### 1 Activity Segregation & Error Classification

Temporal activities encapsulate all non-deterministic side effects (HTTP REST requests):

* **Forward Activities:** `reserve_flight`, `reserve_hotel`, `charge_payment`, `confirm_flight`, `confirm_hotel`.
* **Compensating Activities:** `cancel_flight`, `cancel_hotel`, `refund_payment`.

A critical engineering challenge in workflow design is error classification:

* **Transient Network Failures (Retryable):** If a service is briefly unreachable due to network blips (`httpx.RequestError`), the activity raises a standard error, allowing Temporal's `RetryPolicy` to automatically retry with exponential backoff.
* **Deterministic Domain Rejections (Non-Retryable):** If a service returns `400 Bad Request` (insufficient funds) or `409 Conflict` (already booked), retrying is useless. The activity raises `ApplicationError(..., non_retryable=True)`, immediately failing the activity and triggering the Saga rollback without delay.

> [Attach: Code snippet of charge_payment_activity in activities.py showing the distinction between network RequestError and non_retryable ApplicationError on HTTP 400]

### 2 Deterministic Workflow & Dynamic LIFO Compensation Stack

The `BookingWorkflow` coordinates the transaction lifecycle:

1. As each forward activity completes successfully, its corresponding compensating activity is pushed onto an in-memory **LIFO (Last-In, First-Out) stack**.
2. If any step fails or is rejected, the workflow enters an `except Exception` block.
3. The workflow unwinds the stack in reverse order, executing compensations one by one.
4. If all compensations succeed, the workflow returns `status='COMPENSATED'` along with the complete audit trail of what was reserved and what was rolled back.

> [Attach: Code snippet of workflows.py showing the try/except block, the LIFO compensations stack, and the reverse compensation execution loop]

### 3 Decoupled Gateway Mediation & Scenario Profiles

To make testing and demonstration repeatable, I implemented the `gateway/` module:

* **On-Demand Healthcheck (`health.py`):** Queries `/health` on all three microservices and checks gRPC connectivity to Temporal (:7233) on demand when requested by `--health`.
* **Scenario Profiles (`scenarios.py`):**
  * `happy_path`: Customer `user_1`, total price $400 $\rightarrow$ completes and confirms all steps (`CONFIRMED`).
  * `fail_hotel`: Negative price triggering `422 Unprocessable` at Hotel service $\rightarrow$ triggers flight cancellation (`COMPENSATED`).
  * `fail_payment`: Price $2500 on customer with $1000 balance $\rightarrow$ triggers hotel and flight cancellations in LIFO order (`COMPENSATED`).
* **Unified Dispatcher (`dispatcher.py`):** Connects to Temporal, submits the workflow, and packages the result into a clean `BookingResponse` with a direct link to the Temporal Web UI.

> [Attach: Code snippet of dispatcher.py and scenarios.py showing the resolution of scenario parameters and workflow dispatching]

### 4 Automated Time-Skipping Test Harness

To test distributed workflows without relying on slow sleep timers or live cluster setup in CI, I wrote an automated integration test suite in `tests/test_booking_saga.py`:

* Leverages `temporalio.testing.WorkflowEnvironment.start_time_skipping()`.
* Combines Temporal's in-memory server with `respx` to mock external microservice HTTP responses.
* Runs tests at in-memory speed (all 3 scenarios execute in **0.60 seconds**).
* Uses `temporalio.contrib.pydantic.pydantic_data_converter` for native Pydantic v2 payload serialization.

> [Attach: Screenshot of terminal running pytest -v in orchestrators/temporal showing 3 passed integration tests in under 1 second]

---

## Key Decisions and What I Validated

### Saga Pattern vs. Two-Phase Commit (2PC)

Traditional distributed transaction models like 2-Phase Commit (2PC) require distributed locking across databases. In a microservices environment, 2PC is an anti-pattern:

* It couples services together synchronously.
* If the coordinator crashes while holding locks, resources remain frozen across all databases.

By adopting the **Saga Pattern**, each microservice commits its local transaction immediately inside its own database. If a subsequent step fails, compensating actions (`/cancel`, `/refund`) undo the effects semantically. This maximizes availability and service autonomy.

### Dynamic LIFO Stack vs. Hardcoded Nested Try/Catch

A naive approach to error recovery is nesting `try/except` blocks inside procedural code. As the number of steps increases, nested error handling becomes unmaintainable ("Pyramid of Doom").

I utilized a dynamic **LIFO compensation stack**:

```python
compensations.append((cancel_flight_activity, flight_cancel_req, 'cancel_flight'))
```

When an error occurs at step $N$, the rollback engine simply iterates `reversed(compensations)`:

* Flight succeeded, Hotel failed $\rightarrow$ runs `cancel_flight`.
* Flight succeeded, Hotel succeeded, Payment failed $\rightarrow$ runs `cancel_hotel`, then `cancel_flight`.

The rollback logic is clean, scalable to any number of steps, and automatically adapts to where the failure occurred.

### Validating Recovery in Temporal Web UI

I verified the workflow's real-time visibility using the Temporal Web UI (`http://localhost:8233`):

> [Attach: Screenshot of Temporal Web UI showing the event history of a COMPENSATED workflow, highlighting the failed payment activity followed by the successful cancel_hotel and cancel_flight compensation activities]

The event history provides an immutable audit log: exact timestamps, payloads, retry attempts, and rollback outcomes are permanently visible for debugging and compliance.

---

## From Proof of Concept to Next Cycle (Cycle 4: Naive Baseline Comparison)

With Cycle 3 complete, the Temporal Saga Orchestrator is fully implemented, verified with automated tests, and accessible via the CLI client:

```bash
# Verify system health
uv run python clients/cli.py --health

# Run Happy Path booking
uv run python clients/cli.py --scenario happy_path

# Run Payment Failure rollback demo
uv run python clients/cli.py --scenario fail_payment
```

> [Attach: Screenshot of terminal running clients/cli.py with --scenario fail_payment showing forward steps, LIFO compensations, and status COMPENSATED]

This directly unlocks **Cycle 4 (Naive Baseline & React UI Dashboard)**:

1. I will implement `orchestrators/naive/` (the fragile baseline that does not compensate on process crashes).
2. I will build the React (Vite) single-page dashboard.
3. Because the `gateway/` layer already defines the unified contract, the UI can trigger either the Naive or Temporal orchestrator with identical parameters, setting up the head-to-head reliability experiment.

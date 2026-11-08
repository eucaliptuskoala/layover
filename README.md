# Layover

> **Distributed Transaction Reliability & Workflow Orchestration Experiment**  
> Comparing in-memory Saga execution against durable workflow orchestration (Temporal) under controlled partial failure.

---

## Overview

When building distributed systems, partial failures are inevitable: network timeouts, process crashes, and unhandled exceptions can strike mid-transaction. Without proper coordination, systems are left in an inconsistent "zombie" state (for instance, a flight seat and hotel room are reserved, but payment fails and holds are never released).

**Layover** is a study comparing two approaches to multi-service distributed workflows:

1. **In-Memory Saga Baseline:** Direct HTTP coordination (`Flight -> Hotel -> Payment`) maintaining an in-memory LIFO compensation stack in `try/except`.
2. **Durable Saga (Temporal):** Orchestrated execution implementing the **Saga pattern** backed by a persistent event-sourcing engine with automated retries and durable compensating rollbacks.

Full personal development plan, learning outcomes, and research cycle details can be found in [docs/pdp.md](docs/pdp.md).

---

## Architecture

The project consists of three independent microservices following the **database-per-service** pattern, a coordinator layer, and a control UI:

```text
                  +-----------------------------------+
                  |      React Frontend (Vite)        |
                  |  - Booking Form                   |
                  |  - Engine & Scenario Selection    |
                  |  - Reported Booking Outcomes      |
                  +-----------------+-----------------+
                                    |
                          [ API Gateway :8000 ]
                       (Strategy dispatch by engine)
                                    |
                    +---------------+---------------+
                    |                               |
                    v                               v
         [ In-Memory Saga ]               [ Temporal Workflow ]
       (Ad-Hoc LIFO Rollbacks)            (Durable Saga Runner)
                    |                               |
                    +---------------+---------------+
                                    |
           +------------------------+------------------------+
           |                        |                        |
           v                        v                        v
  +------------------+     +------------------+     +------------------+
  |  Flight Service  |     |  Hotel Service   |     | Payment Service  |
  |     (:8001)      |     |     (:8002)      |     |     (:8003)      |
  |    flight.db     |     |     hotel.db     |     |    payment.db    |
  +------------------+     +------------------+     +------------------+
```

### Services

| Service             | Port   | Database              | Endpoints                                                                          |
| :------------------ | :----- | :-------------------- | :--------------------------------------------------------------------------------- |
| **Flight Service**  | `8001` | `flight.db` (SQLite)  | `POST /reserve`, `POST /confirm`, `POST /cancel`, `GET /reservations/{booking_id}` |
| **Hotel Service**   | `8002` | `hotel.db` (SQLite)   | `POST /reserve`, `POST /confirm`, `POST /cancel`, `GET /reservations/{booking_id}` |
| **Payment Service** | `8003` | `payment.db` (SQLite) | `POST /charge`, `POST /refund`                                                     |

### Engine behavior

`POST /api/bookings` accepts `orchestrator: 'temporal' | 'naive'`. The gateway resolves the
scenario once and selects `TemporalSagaStrategy` or `NaiveSagaStrategy` from `STRATEGIES`.
Both execute `reserve_flight → reserve_hotel → charge_payment → confirm_flight → confirm_hotel`.

- **Naive:** one HTTP attempt per action, with a request-local LIFO compensation stack. The
  API coordinator runs in the gateway process. After an acknowledged charge, rollback order is
  `refund_payment → cancel_hotel → cancel_flight`. A payment decline only cancels hotel then flight.
  The coordinator attempts remaining rollbacks even when one fails. It has no persistent queue,
  booking registry, restart recovery, distributed lock, or direct database access.
- **Temporal:** the existing workflow keeps three forward activity attempts and five compensation
  attempts for retryable failures. Worker crashes can trigger replay and activity retries while
  Temporal remains available. Existing HTTP-rejection classification and workflow behavior are unchanged.

Naive reports `CONFIRMED` after all five actions, `COMPENSATED` after complete rollback of
acknowledged work, and `FAILED` for incomplete rollback or uncertain HTTP outcomes. It records
only acknowledged successful actions. A lost response can hide a committed service action;
`FAILED` therefore does not prove that no state changed.

Both reservation services reject cancellation after `CONFIRMED`. A failure during confirmation
can leave partial state. Temporal currently reports `COMPENSATED` even if a compensation fails;
the UI flags completed actions without matching reported rollbacks. Compare service state, not
just the top-level outcome. The current Temporal dev server stores history in memory, so keep
it alive during worker-crash experiments; server-restart persistence is outside this baseline.

---

## Prerequisites

- **Python:** 3.11 or newer (managed via `uv`)
- **Package Manager:** [`uv`](https://docs.astral.sh/uv/)
- **Temporal CLI:** For running the local development server ([installation guide](https://docs.temporal.io/cli))
- **Node.js:** See [ui/README.md](ui/README.md) for supported versions and frontend setup
- **Docker Compose:** For the full local stack; not required for isolated Python integration tests

---

## Getting Started

### 1. Clone & Set Up Python Environment

Each microservice, orchestrator, and client module is an independent package with its own virtual environment:

```bash
# Clone the repository
git clone <repo-url>
cd layover

# Sync dependencies across all subprojects
for d in services/* orchestrators/naive orchestrators/temporal gateway clients; do (cd "$d" && uv sync); done
```

### 2. Configure Environment

Copy `.env.example` to `.env` (already done by default):

```bash
cp .env.example .env
```

### 3. Run the Test Suite

Run unit and contract tests from each independent project:

```bash
# Run tests across all services and orchestrators
for d in services/* orchestrators/naive orchestrators/temporal gateway; do (cd "$d" && uv run pytest); done

# Or run tests for a single service:
cd services/flight && uv run pytest
```

Live gateway tests and `SIGKILL` comparisons are opt-in. They create fresh databases,
ephemeral loopback ports, and owned subprocesses, without resetting existing Compose volumes:

```bash
uv run --directory gateway pytest --run-integration tests/integration -v -s
```

See [the integration test guide](gateway/tests/integration/README.md) for prerequisites,
the exact crash checkpoint, and evidence output. Frontend checks live in [ui/README.md](ui/README.md).

### 4. Run Services via Docker Compose

Build and launch the microservices, Temporal dev server, worker, and gateway:

```bash
# Build and start services in the background
docker compose up -d --build

# Inspect status and healthcheck results
docker compose ps

# View aggregated logs
docker compose logs -f

# Stop services
docker compose down
```

The gateway build uses the repository root as its context so it can install the sibling
`orchestrators/naive` package. It copies only gateway and naive code. After code changes:

```bash
docker compose up -d --build gateway
```

### 5. Alternative: Local Python Processes

Use this instead of full-stack Compose, or start only the three services with
`docker compose up -d flight-service hotel-service payment-service`. Do not also launch
local Temporal or gateway processes on ports already used by Compose.

For local Temporal:

```bash
temporal server start-dev --namespace layover
```

This starts a lightweight, single-binary Temporal cluster, automatically creates the `layover` namespace, and launches the Web UI at [http://localhost:8233](http://localhost:8233).

### 6. Start Local Worker and Gateway

In a separate terminal tab, run the worker listening for booking workflows on `booking-task-queue`:

```bash
# Run directly from repository root:
uv run --directory orchestrators/temporal python worker.py

# Or by navigating into the orchestrator directory:
cd orchestrators/temporal && uv run python worker.py
```

Start the gateway in another terminal:

```bash
uv run --directory gateway python main.py
```

Naive bookings need the three services and gateway, but no running Temporal server or worker.

### 7. Dispatch Bookings via CLI Client

In another terminal, use the CLI client to check system health or execute booking scenarios:

The existing CLI imports the gateway dispatcher rather than calling the gateway over HTTP.
Naive CLI runs therefore keep their compensation stack in the CLI process and do not need a
running gateway. The crash harness tests API bookings, so it kills the gateway for naive.

```bash
# On-demand health check across all microservices and Temporal
uv run --directory clients python cli.py --health

# Execute Happy Path booking (expect CONFIRMED)
uv run --directory clients python cli.py --scenario happy_path

# Run the same booking through the in-memory baseline
uv run --directory clients python cli.py --scenario happy_path --orchestrator naive

# Demonstrate Saga Rollback on Payment failure (Insufficient Funds -> COMPENSATED)
uv run --directory clients python cli.py --scenario fail_payment

# Demonstrate Saga Rollback on Hotel rejection (COMPENSATED)
uv run --directory clients python cli.py --scenario fail_hotel

# Or navigate to clients directory first:
cd clients && uv run python cli.py --health
```

---

## Project Structure

```text
layover/
├── services/                  # Autonomous Microservices (FastAPI & SQLite)
│   ├── flight/                # Port 8001 (flight.db)
│   ├── hotel/                 # Port 8002 (hotel.db)
│   └── payment/               # Port 8003 (payment.db)
│
├── orchestrators/             # Workflow Coordinators
│   ├── naive/                 # Installable layover_naive package, volatile coordinator & tests
│   └── temporal/              # Temporal Saga Orchestrator (Workflows, Activities, Worker)
│
├── gateway/                   # Application Service Layer (Contracts, Scenarios, Health)
│   ├── models.py              # Unified BookingRequest & BookingResponse schemas
│   ├── scenarios.py           # Predefined test scenario profiles
│   ├── health.py              # On-demand healthcheck engine
│   ├── dispatcher.py          # Strategy interface, concrete engines, and dispatch context
│   └── tests/integration/     # Isolated live-stack and deterministic coordinator-crash tests
│
├── clients/                   # Consumer Adapters
│   └── cli.py                 # Command-line interface with pre-flight & scenario flags
│
├── ui/                        # React booking UI; engine selection and saved result summaries
│
├── docs/                      # Personal Development Plan & Portfolio Evidences
│   ├── pdp.md                 # 5-Cycle Research & Learning Outcomes plan
│   └── evidences/             # Portfolio evidence documents (LO1, LO2, LO3)
│
├── docker-compose.yml         # Container orchestration with healthchecks & volumes
├── ruff.toml                  # Pragmatic linter configuration
└── AGENTS.md                  # Workspace guidelines for AI pair programming
```

---

## License

Academic / Personal Project — Semester 2026.

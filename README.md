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
                  |      React Frontend (Vite :5173)  |
                  |  - Booking Sandbox                |
                  |  - Engine & Scenario Selection    |
                  |  - Real-time State Topology       |
                  +-----------------+-----------------+
                                    |
                           [ API Gateway :8000 ]
                     (Stateless Strategy Dispatcher)
                                    |
                    +---------------+---------------+
                    | (HTTP :8004)                  | (gRPC :7233)
                    v                               v
         [ Naive Orchestrator ]           [ Temporal Cluster ]
         (Standalone microservice)        (Durable History Engine)
         (In-Memory LIFO Stack)                     |
                    |                     [ Temporal Worker ]
                    |                     (Workflow Activities)
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

### Services & Components

| Component | Port | Persistence | Primary Endpoints / Role |
| :--- | :--- | :--- | :--- |
| **API Gateway** | `8000` | Stateless | `POST /api/bookings`, `GET /health`, `GET /scenarios` |
| **Flight Service** | `8001` | `flight.db` (SQLite) | `POST /reserve`, `POST /confirm`, `POST /cancel`, `GET /health` |
| **Hotel Service** | `8002` | `hotel.db` (SQLite) | `POST /reserve`, `POST /confirm`, `POST /cancel`, `GET /health` |
| **Payment Service** | `8003` | `payment.db` (SQLite) | `POST /charge`, `POST /refund`, `GET /health` |
| **Naive Orchestrator** | `8004` | In-Memory RAM | `POST /book`, `GET /health` |
| **Temporal Cluster** | `7233`<br/>`8233` | SQLite (Dev) | gRPC Engine (`:7233`) and Web UI Dashboard (`:8233`) |
| **Temporal Worker** | None | Event Log | Consumes workflows & activities from `booking-task-queue` |
| **React UI Dashboard** | `5173` | Local Storage | Interactive developer sandbox & topology visualizer |

### Engine Behavior

The API Gateway (`POST /api/bookings`) accepts `orchestrator: 'temporal' | 'naive'`. The gateway selects `TemporalSagaStrategy` or `NaiveSagaStrategy` from `STRATEGIES`:

- **Naive (`layover-naive` on port `:8004`):** An autonomous microservice executing steps sequentially (`reserve_flight → reserve_hotel → charge_payment → confirm_flight → confirm_hotel`). It registers compensations in an in-memory LIFO stack in process RAM. If an error occurs (such as HTTP 400 Insufficient Funds), it executes compensations in reverse order (`cancel_hotel → cancel_flight`). However, if the `layover-naive` container is terminated mid-flight (`docker kill layover-naive`), the compensation stack in RAM is destroyed, leaving orphaned holds in SQLite.
- **Temporal (`layover-worker` via `layover-temporal`):** Orchestrated execution backed by Temporal's append-only event history. Each step and compensation is an isolated activity with exponential retries. If the worker process is killed mid-booking, the pending workflow is preserved in Temporal Server and automatically resumes upon worker restart.

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

All services use strictly scoped build contexts and cached `uv` dependency layers. To rebuild any specific service after code changes:

```bash
docker compose up -d --build gateway
docker compose up -d --build naive-orchestrator
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
│   ├── naive/                 # Standalone In-Memory Saga Orchestrator (:8004, volatile RAM stack)
│   └── temporal/              # Temporal Saga Orchestrator (Workflows, Activities, Worker)
│
├── gateway/                   # Stateless API Gateway & Facade (:8000)
│   ├── models.py              # Unified BookingRequest & BookingResponse schemas
│   ├── scenarios.py           # Predefined test scenario profiles
│   ├── health.py              # On-demand healthcheck engine
│   ├── dispatcher.py          # Strategy interface, concrete engines, and dispatch context
│   └── tests/                 # Unit & dispatcher mocks (isolated live tests in integration/)
│
├── clients/                   # Consumer Adapters
│   └── cli.py                 # Command-line interface with pre-flight & scenario flags
│
├── ui/                        # React 19 UI Dashboard (:5173); interactive sandbox & state visualizer
│
├── docs/                      # Personal Development Plan, Cycle Reports & Portfolio Evidences
│   ├── pdp.md                 # 5-Cycle Research & Learning Outcomes plan
│   ├── cycle-1.md             # Cycle 1 Research & Problem Scoping report
│   ├── cycle-4.md             # Cycle 4 Baseline In-Memory & UI Dashboard report
│   └── evidences/             # Portfolio evidence documents (LO1, LO2, LO3)
│
├── docker-compose.yml         # Container orchestration with healthchecks & volumes
├── ruff.toml                  # Pragmatic linter configuration
└── AGENTS.md                  # Workspace guidelines for AI pair programming
```

---

## License

Academic / Personal Project — Semester 2026.

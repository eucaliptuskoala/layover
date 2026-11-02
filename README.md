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
                  |  - Live Status Cards              |
                  |  - Crash Simulation Toggle        |
                  +-----------------+-----------------+
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

| Service | Port | Database | Endpoints |
| :--- | :--- | :--- | :--- |
| **Flight Service** | `8001` | `flight.db` (SQLite) | `POST /reserve`, `POST /cancel` |
| **Hotel Service** | `8002` | `hotel.db` (SQLite) | `POST /reserve`, `POST /cancel` |
| **Payment Service** | `8003` | `payment.db` (SQLite) | `POST /charge`, `POST /refund` |

---

## Prerequisites

- **Python:** 3.11 or newer (managed via `uv`)
- **Package Manager:** [`uv`](https://docs.astral.sh/uv/)
- **Temporal CLI:** For running the local development server ([installation guide](https://docs.temporal.io/cli))
- **Node.js:** For the React / Vite frontend (Cycle 3)

---

## Getting Started

### 1. Clone & Set Up Python Environment

Each microservice, orchestrator, and client module is an independent package with its own virtual environment:

```bash
# Clone the repository
git clone <repo-url>
cd layover

# Sync dependencies across all subprojects
for d in services/* gateway orchestrators/temporal clients; do (cd "$d" && uv sync); done
```

### 2. Configure Environment

Copy `.env.example` to `.env` (already done by default):

```bash
cp .env.example .env
```

### 3. Run the Test Suite

Run the full automated test suite (35 tests) across all microservices and the Temporal saga orchestrator:

```bash
# Run tests across all services and orchestrators
for d in services/* orchestrators/temporal; do echo "=== $d ===" && (cd "$d" && uv run pytest); done

# Or run tests for a single service:
cd services/flight && uv run pytest
```

### 4. Run Services via Docker Compose

To build and launch all three microservices with healthchecks and isolated persistent volumes:

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

### 5. Start Local Temporal Server

For durable workflow orchestration (Cycle 3):

```bash
temporal server start-dev --namespace layover
```

This starts a lightweight, single-binary Temporal cluster, automatically creates the `layover` namespace, and launches the Web UI at [http://localhost:8233](http://localhost:8233).

### 6. Start Temporal Worker

In a separate terminal tab, run the worker listening for booking workflows on `booking-task-queue`:

```bash
# Run directly from repository root:
uv run --directory orchestrators/temporal python worker.py

# Or by navigating into the orchestrator directory:
cd orchestrators/temporal && uv run python worker.py
```

### 7. Dispatch Bookings via CLI Client

In another terminal, use the CLI client to check system health or execute booking scenarios:

```bash
# On-demand health check across all microservices and Temporal
uv run --directory clients python cli.py --health

# Execute Happy Path booking (expect CONFIRMED)
uv run --directory clients python cli.py --scenario happy_path

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
│   └── temporal/              # Temporal Saga Orchestrator (Workflows, Activities, Worker)
│
├── gateway/                   # Application Service Layer (Contracts, Scenarios, Health)
│   ├── models.py              # Unified BookingRequest & BookingResponse schemas
│   ├── scenarios.py           # Predefined test scenario profiles
│   ├── health.py              # On-demand healthcheck engine
│   └── dispatcher.py          # Unified booking dispatcher
│
├── clients/                   # Consumer Adapters
│   └── cli.py                 # Command-line interface with pre-flight & scenario flags
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

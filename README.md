# Layover

> **Distributed Transaction Reliability & Workflow Orchestration Experiment**  
> Comparing naive sequential execution against durable workflow orchestration (Temporal) under controlled partial failure.

---

## Overview

When building distributed systems, partial failures are inevitable: network timeouts, process crashes, and unhandled exceptions can strike mid-transaction. Without proper coordination, systems are left in an inconsistent "zombie" state (for instance, a flight seat and hotel room are reserved, but payment fails and holds are never released).

**Layover** is a study comparing two approaches to multi-service workflows:

1. **Naive Baseline:** Direct sequential HTTP calls (`Flight -> Hotel -> Payment`) with simple in-process error handling.
2. **Durable Workflow (Temporal):** Orchestrated execution implementing the **Saga pattern** with automated retry and compensating rollbacks.

Full personal development plan, learning outcomes, and research cycle details can be found in [pdp.md](pdp.md).

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
         [ Naive Coordinator ]            [ Temporal Workflow ]
           (Direct HTTP calls)             (Durable Saga Runner)
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

```bash
# Clone the repository
git clone <repo-url>
cd layover

# Sync virtual environment and dependencies using uv
uv sync
```

### 2. Configure Environment

Copy `.env.example` to `.env` (already done by default):

```bash
cp .env.example .env
```

### 3. Run the Test Suite

```bash
uv run pytest
```

### 4. Start Local Temporal Server

For workflow orchestration in Cycle 4:

```bash
temporal server start-dev
```

This starts a lightweight, single-binary Temporal cluster and launches the Web UI at [http://localhost:8233](http://localhost:8233).

---

## Project Structure

```text
layover/
├── pdp.md             # Personal Development Plan (Cycles, Goals, LOs)
├── pyproject.toml     # Project dependencies and config managed by uv
├── .env.example       # Example environment variables
├── .env               # Local environment variables
├── .gitignore         # Git ignore rules
├── AGENTS.md          # Workspace guidelines for AI pair programming
└── README.md          # Project documentation
```

---

## License

Academic / Personal Project — Semester 2026.

# Docker Containerization & Multi-Service Orchestration

## Introduction

> Built and orchestrated production-ready, lightweight Docker containers for the Flight, Hotel, and Payment microservices using Astral uv, layered dependency caching, declarative Compose healthchecks, and isolated persistent volumes.

---

## Context and the Problem

Running distributed microservices exclusively via local terminal sessions (`uv run uvicorn ...`) works during early prototyping, but presents severe operational challenges as system complexity grows:

* **Environment Drift:** Differences between local operating systems (macOS vs. Linux on CI/production), installed Python patch versions, and system C-libraries lead to subtle runtime discrepancies.
* **Manual Operational Overhead:** Launching three microservices concurrently requires opening three separate terminal tabs, setting environment variables manually, and remembering exact port allocations (`8001`, `8002`, `8003`).
* **Resource Leakage and Unclean State:** When restarting services locally, abandoned SQLite files or background processes can hold locks or retain outdated test records, masking real integration issues.

To satisfy **Software Maintenance & Delivery (LO3)**, I needed a reproducible, containerized deployment setup that packages each microservice with its exact locked dependencies, orchestrates multi-container lifecycles with health checks, and preserves strict database-per-service isolation across restarts.

---

## Systems Thinking: How It Fits the Project

Containerization reinforces the architectural boundaries established in Cycle 2:

> [Attach: Architecture diagram showing Docker Compose orchestrating Flight, Hotel, and Payment containers, with isolated named volumes and port mappings 8001, 8002, and 8003]

* **Autonomous Container Artifacts:** Each microservice folder owns its own `Dockerfile` and `pyproject.toml`. A service can be built, tested, and deployed independently without knowledge of the other two services.
* **Declarative Orchestration (`docker-compose.yml`):** A single declarative manifest defines the desired state of the system—service startup order, environment variables, health status monitoring, and network port forwarding.
* **Physical Persistence Isolation:** Rather than sharing a database directory, each container mounts an isolated named volume (`layover-flight-data`, `layover-hotel-data`, `layover-payment-data`). Even in containerized form, no service can inspect or corrupt another service's database.

---

## Progressive Engineering Steps

I containerized and orchestrated the system across four progressive iterations:

### 1 Base Image Selection & Layered Dependency Caching (`uv`)

Standard Dockerfiles using `pip install` often result in slow builds (1–2 minutes) and bulky images (> 400 MB).

I designed each `Dockerfile` around `python:3.11-slim` combined with Astral's official `uv` binary:

> [Attach: Code snippet of services/flight/Dockerfile showing COPY --from=ghcr.io/astral-sh/uv, layer-cached uv sync, and non-root execution path]

By copying `pyproject.toml` and `uv.lock` first and running `uv sync --frozen --no-dev --no-install-project`, the dependency layer is cached. When application code changes, Docker reuses the cached layer, rebuilding the container image in under 1 second.

### 2 Microservice Isolation & Build Context Management

To prevent local development artifacts (`.venv`, `__pycache__`, `.pytest_cache`, and temporary SQLite `.db` files) from leaking into the container images, I established a centralized `.dockerignore`:

> [Attach: Code snippet of .dockerignore showing excluded directories, virtual environments, and SQLite database patterns]

This guarantees that container builds are clean and deterministic, compiling only pristine source files and locked dependencies.

### 3 Declarative Multi-Service Orchestration via Docker Compose

I authored a declarative `docker-compose.yml` manifest coordinating the three services:

* **Port Mapping:** Exposes `8001` (Flight), `8002` (Hotel), and `8003` (Payment) for external coordinator access.
* **Database Volume Anchoring:** Configures environment variables (`FLIGHT_DB_PATH=/app/data/flight.db`, etc.) pointing to dedicated volume mount points (`/app/data/`).
* **Automated Healthchecks:** Configured periodic healthchecks pinging the `/health` endpoint of each service every 10 seconds.

> [Attach: Code snippet of docker-compose.yml showing service definitions, port mappings, environment overrides, and healthchecks]

### 4 Continuous Build Verification in CI

To ensure Docker build manifests never break silently as code evolves, I updated the GitHub Actions matrix workflow (`.github/workflows/ci.yml`).

> [Attach: Code snippet of .github/workflows/ci.yml showing the Build Docker image step running across the parallel matrix runners]

After running lint checks and the `pytest` suite, each matrix runner builds its respective Docker image (`docker build -t <service>-service:latest .`), validating buildability on every commit.

---

## Key Decisions and What I Validated

### Ephemeral `uv` Binary Injection vs. Standard `pip`

Rather than running `pip install uv` (which requires downloading wheels and bloats the layer), I copied the pre-compiled, statically linked `uv` binary directly from `ghcr.io/astral-sh/uv:latest`:

```dockerfile
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
```

* Eliminates network overhead during package manager setup.
* Uses `--frozen` to enforce bit-for-bit reproducibility against `uv.lock`.
* Omits development tools (`pytest`) from the runtime image (`--no-dev`), keeping image footprint compact.

### Python Built-in HTTP Healthchecks vs. Extra System Utilities

In `python:3.11-slim`, system utilities like `curl` and `wget` are excluded by default. Installing them via `apt-get install curl` adds unnecessary security attack surface and image bloat.

I leveraged Python's standard library `urllib.request` directly inside the Docker Compose healthcheck test:

```yaml
test: ["CMD", "python3", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"]
```

This validates both that the container process is alive and that the Python runtime can serve HTTP requests, without adding a single byte of third-party software.

### Isolated Named Volumes for Database-per-Service Persistence

A container's filesystem is ephemeral by default. If a container stops or restarts, unmounted database files disappear.

I configured three independent named volumes (`flight-data`, `hotel-data`, `payment-data`). This ensures:
1. Data persists across `docker compose restart` or container rebuilds.
2. Complete physical isolation: the Flight container cannot mount or access `payment-data`.

---

## From Proof of Concept to Next Cycle

With Docker containerization complete, the entire backend can be brought up with a single command:

```bash
docker compose up -d --build
```

> [Attach: Screenshot of terminal running docker compose up --build showing three green containers starting and passing healthchecks]

This provides a stable, reproducible foundation for **Cycle 3 (Temporal Saga Orchestrator)** and **Cycle 4 (Naive Sequential Coordinator)**. When running workflow failure simulations and chaos benchmarks, we can launch, reset, and tear down the entire multi-service topology cleanly in seconds.

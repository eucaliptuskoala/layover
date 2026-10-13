# Continuous Integration Pipeline (GitHub Actions Matrix)

## Introduction

> Implemented an autonomous GitHub Actions CI pipeline using a matrix strategy to concurrently lint and run automated test suites across all three microservices on every commit, enforcing continuous validation and maintainable delivery.

---

## Context and the Problem

During early development, it is easy to rely on local test runs: running `pytest` in your terminal and assuming everything works. However, "works on my machine" is not sustainable engineering.

Local environments often hide critical issues:

* Leftover local SQLite files or environment variables can mask test failures that would appear on a clean machine.
* A developer working on one service (e.g. `services/payment/`) might unintentionally push a change that breaks another service without noticing.
* When working towards portfolio deliverables, teachers expect repeatable evidence that software quality is verified automatically on a clean runner.

Originally, the repository had a simple GitHub Actions workflow designed for a single Python project. Once I split the codebase into three true microservices with independent directories, that workflow broke completely: it looked for a root `pyproject.toml` that no longer existed and had no steps to run tests.

I needed an automated Continuous Integration (CI) pipeline that mirrors our microservice architecture, runs quality checks on every push and pull request, and provides clear, immediate feedback if any service fails.

---

## Systems Thinking: How It Fits the Project

A continuous integration pipeline should reflect the architectural boundaries of the system it builds.

Because Layover is built on autonomous microservices with independent dependency trees, the CI pipeline was designed around an independent **Matrix Strategy**:

> [Attach: Diagram or screenshot showing the GitHub Actions Matrix Dispatcher executing three parallel jobs for Flight, Hotel, and Payment concurrently]

Every service runs in its own isolated Ubuntu container:

* Upstream, it triggers on every `push` and `pull_request` targeting `main`.
* Downstream, it guarantees that no broken code enters the main branch, creating a verifiable record of passing tests for portfolio reviews.

---

## Progressive Engineering Steps

I set up and refined the CI pipeline across four clear iterations:

### 1 Diagnosing the Legacy Workflow Breakdown

The repository originally contained a single `.github/workflows/ci.yml` that attempted to run `uv sync --all-groups` in the repository root.

When I checked the configuration, I identified two fundamental flaws:

1. Since each service now owns its own `pyproject.toml` inside `services/<service>/`, running `uv sync` in the root threw an immediate error.
2. The legacy workflow only checked formatting with Ruff and never executed `pytest`. A build could pass CI while all API endpoints were broken.

### 2 Defining a Pragmatic Linter Configuration (`ruff.toml`)

Before enforcing linting in CI, I tested `ruff` against our service code and found that standard rules flagged harmless lines (such as 90-character SQL queries or Pydantic field descriptions) because the default limit is 88 characters.

Rather than cluttering clean SQL queries with artificial line breaks, I added a root configuration file `ruff.toml`:

> [Attach: Code snippet of ruff.toml showing line-length, selected rules (E, F, W), and ignored rules (E501)]

* `E, W`: Catches real syntax and formatting mistakes from PEP 8.
* `F`: Catches critical Pyflakes bugs (unused imports, misspelled variables, undefined functions).
* `ignore = ["E501"]`: Silences line-length complaints for readable SQL strings and exception messages.

### 3 Implementing Concurrent Matrix Testing

Instead of writing three separate repetitive jobs or running a sequential bash script (`cd flight && pytest ... && cd hotel ...`), I implemented a GitHub Actions matrix job:

> [Attach: Code snippet of .github/workflows/ci.yml showing the matrix configuration and per-service working-directory definition]

This instructs GitHub Actions to launch three Ubuntu runners concurrently. Each runner receives a different value for `${{ matrix.service }}` and sets its working directory directly to `services/<service>/`.

### 4 Consolidating Per-Service Autonomy

Initially, one might consider running a single global lint check across all folders, followed by separate test runs. However, that creates an unnecessary coupling: a formatting issue in the Flight service would block the Payment service from running its test suite.

I consolidated each service's quality checks into an autonomous execution sequence:

1. `uvx ruff check .`: Validates style and syntax for that specific microservice.
2. `uv sync`: Installs the service's exact locked dependencies from its own `uv.lock`.
3. `uv run pytest -v`: Executes all unit and integration tests for that service.

---

## Key Decisions and What I Validated

### Matrix Execution vs. Monolithic Sequential Script

I deliberately used GitHub Actions `strategy.matrix` rather than running a sequential loop in a single runner.

In a sequential setup, if `services/flight/` fails its tests, the entire pipeline terminates early, leaving developers with zero visibility into whether `hotel` and `payment` were healthy.

With the matrix strategy:

* Each microservice runs on a separate clean Ubuntu VM concurrently.
* If a bug is pushed to `payment`, only `Verify (payment)` turns red. `Verify (flight)` and `Verify (hotel)` finish and report green.
* The failure is cleanly isolated, matching how independent microservices operate in production teams.

### Fast Ephemeral Execution with `uvx` and `setup-uv` Caching

Speed is essential in CI: slow pipelines discourage developers from pushing frequent commits.

I leveraged Astral's official `astral-sh/setup-uv@v5` action with `enable-cache: true`:

* Dependency wheels are cached across CI runs, reducing dependency installation to 2–3 seconds.
* `uvx ruff check .` runs Ruff ephemerally without needing `ruff` listed as a permanent project dependency in each service's `pyproject.toml`.

As a result, each microservice job finishes in under 20 seconds, providing rapid, reliable feedback.

---

## From Proof of Concept to Next Cycle

The updated CI workflow now protects the repository on every push:

> [Attach: Screenshot of GitHub Actions workflow run showing all three matrix jobs (Flight, Hotel, Payment) passing green with checkmarks]

All 32 automated tests pass, and code quality is validated automatically.

As we move into **Cycle 3 (Temporal Saga Orchestrator)** and **Cycle 4 (Naive Sequential Coordinator)**, this CI pipeline will immediately flag if any workflow orchestrator accidentally introduces breaking contract changes to the microservices.

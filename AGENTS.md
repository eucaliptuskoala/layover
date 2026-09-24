# Agent Guidelines for Layover

This document defines core conventions, architectural rules, and coding preferences for AI assistants working in this repository.

---

## 1. Project Context & Architecture

- **Domain:** Distributed travel booking system studying fault tolerance and workflow reliability under partial failure.
- **Core Comparison:** Naive sequential execution vs. durable workflow orchestration via Temporal (`temporalio` Python SDK).
- **Microservices Principle:** True **database-per-service** isolation. Each service (Flight, Hotel, Payment) owns its own SQLite database file (`flight.db`, `hotel.db`, `payment.db`). No service may directly access or mutate another service's database.
- **Contracts:** Every service must provide both forward actions (`/reserve`, `/charge`) and compensating rollback actions (`/cancel`, `/refund`).

---

## 2. Dependency & Environment Management

- **Manager:** Always use [`uv`](https://docs.astral.sh/uv/) for Python dependencies and execution.
- **Virtual Environment:** Located at `.venv`.
- **Command Execution:**
  - Run scripts via `uv run python <script.py>`.
  - Run tests via `uv run pytest`.
  - Add packages via `uv add <package>` or `uv add --dev <package>`.
- **Never** use global `pip install`.

---

## 3. Code Preferences & Style

- **Strings:** Prefer single quotes (`'string'`) for Python and TypeScript strings unless multi-line or double quotes are required for JSON formatting.
- **Spacing:** Provide generous whitespace between logical code blocks and functions. Avoid squishing lines together.
- **Simplicity:** Keep service implementations lightweight. Each service only requires minimal tables and clear endpoints to model the state machine (`RESERVED`, `CONFIRMED`, `CANCELLED`). Avoid speculative abstractions or complex ORM bloat.
- **Testing:** Every service endpoint and workflow coordinator must have corresponding automated tests using `pytest` and `httpx.AsyncClient`.

---

## 4. Key References

- [pdp.md](pdp.md) — Personal Development Plan, research hypotheses, and cycle roadmap.
- [README.md](README.md) — System architecture, setup instructions, and endpoints table.

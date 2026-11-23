# Collection Description: Layover Distributed Transaction & Reliability Research

## Introduction

This collection covers my first Personal Experiment: comparing a naive sequential implementation of a multi-service travel-booking saga against a Temporal-orchestrated version, under controlled failure injection, to measure the difference in data consistency and recovery behavior. The idea originated from feedback I received after a hackathon, where I ran into exactly this class of problem with a heavy multi-step pipeline and had no clean way to reason about partial failure.

The system consists of three independent microservices (Flight, Hotel, Payment), each with its own SQLite database, plus a React/Vite dashboard to trigger bookings and inject failures. I implement and compare two coordinators — a naive sequential controller (Version A) and a Temporal-based Saga workflow with compensating actions (Version B) — against 5 defined failure scenarios, measuring consistency rate, recovery time, and error-handling complexity.

Personal experiments should have a clear relation to the multiple learning outcomes. Adjust learning outcomes based on your work.

---

## Relation to Learning Outcomes

* **Software Engineering (LO1):** Researching and applying distributed-systems theory (CAP theorem, ACID vs. BASE, 2PC vs. Saga, orchestration vs. choreography) to justify concrete architectural decisions and engineering implementations for this system.
* **Software Quality (LO2):** Defining objective, measurable quality criteria (consistency rate formula, recovery time, error-handling complexity) before running any experiment, and building automated test suites (120 deterministic tests) around both implementations.
* **Software Maintenance (LO3):** Designing the system around service autonomy and database-per-service isolation, containerizing the topology with Docker, building a dual-job GitHub Actions CI pipeline, and exposing explicit, idempotent compensating endpoints.
* **Professional Standard / Advising (LO4):** Producing an evidence-based advisory document (ADR) on when a workflow engine like Temporal is actually justified versus lightweight scripting, based on empirical benchmarks instead of vendor claims.
* **Personal Leadership (LO5):** Managing a strict ~38-hour time budget across structured iterations, facilitating technical peer review, adjusting scope under coaching feedback, and aligning potential project extensions with educators.

---

## Assessment 1 — Problem Scoping & Theoretical Foundations

* **Status:** Delivered & Assessed
* **Scope:** Foundational research, problem definition, testable hypotheses, and personal development planning.

### Evidence Artifacts for Assessment 1

* **Research Foundation (LO1 / LO4):** Researched distributed-systems theory across 10 academic and industry sources (CAP theorem, ACID vs. BASE, 2PC blocking limits, and orchestrator vs. choreographed sagas), translating theory into concrete design rules, 3 falsifiable hypotheses (H1–H3), and 5 formal failure scenarios (SC-01 to SC-05) prior to code implementation @[Cycle 1: Research & Problem Scoping](cycle-1.md)
* **Goal Setting & Scope Control (LO5):** Formulated learning goals across all 5 LOs, structured the 5-cycle research roadmap, and established a strict ~38-hour time budget with clear cutback criteria to prevent speculative scope creep @[Personal Development Plan](pdp.md)
* **Stakeholder Alignment (LO5):** Documented recurring feedback loops with coach (Erik), calibrating technical ambitions and validating sprint boundaries at each milestone @[Feed-Pulse](feedback.md)

---

## Assessment 2 — Empirical Realization, Quality Verification & Architectural Advisory

* **Status:** Complete (Ready for Assessment)
* **Scope:** Full multi-service implementation, dual orchestration engines, 120-test verification pyramid with chaos benchmarking, Docker/CI pipeline, evidence-based ADR, and peer knowledge-sharing review.

### Evidence Artifacts for Assessment 2 (Formatted via Evidence Writing Template)

#### Software Engineering (LO1) — HBO-i: Realizing (Level 3–4)

* Designed and built 3 autonomous microservices (`flight`, `hotel`, `payment`) enforcing physical Database-per-Service isolation (`.db` files) and Compare-And-Swap (CAS) state machine transitions with Pydantic schema validation, preventing shared-database shortcuts that compromise partial-failure research @[Microservices Architecture, Database Isolation & Contract Testing](evidences/lo2/contract-and-integration-testing/lo2-contract-and-integration-testing.md)
* Implemented a single-page reactive dashboard in React 19 / TypeScript / Vite, evaluating polling vs. push feeds to visually render real-time finite state transitions, service latency, and partial rollback cascades during live failure injection @[Reactive Orchestration Dashboard & Typed Client Architecture](evidences/lo1/frontend-dashboard/lo1-frontend-dashboard.md)
* Engineered an autonomous in-memory Saga coordinator (`layover-naive`) using Python LIFO rollback stacks, empirically establishing the operational boundary where procedural `try/except` logic suffices versus where process crashes wipe volatile RAM and cause silent inventory leaks @[Vanilla In-Memory Saga Orchestrator & Volatile Failure Analysis](evidences/lo1/naive-saga-orchestrator/lo1-naive-saga-orchestrator.md)
* Implemented a durable, event-sourced workflow coordinator using the Temporal Python SDK, configuring deterministic activity scheduling with exponential backoffs and compensating rollback handlers to guarantee eventual consistency across microservice boundaries @[Temporal Saga Orchestration & Distributed Compensations](evidences/lo4/adr-orchestrator-selection/lo4-architectural-decision-record.md)

#### Software Quality (LO2) — HBO-i: Quality Management (Level 3–4)

* Designed and executed a 134-test automated verification pyramid—combining mock-free SQLite CAS contract tests, Temporal SDK Replayer determinism verification, and an HTTP chaos barrier proving a 0% vs 100% crash resilience disparity under `SIGKILL`—grounded directly in the formal consistency rate formula established in Assessment 1 @[Contract & Integration Testing: Multi-Tier Quality Harness & Chaos Testing](evidences/lo2/contract-and-integration-testing/lo2-contract-and-integration-testing.md)

#### Software Maintenance (LO3) — HBO-i: Managing & Maintaining (Level 3)

* Containerized the 7-service topology using multi-stage Alpine/Slim builds, native Python `urllib` healthcheck probes, and isolated named Docker volumes, enforcing strict physical Database-per-Service boundaries to prevent host-OS file-locking conflicts and cross-service data contamination @[Docker Containerization & Multi-Service Topology: 7-Container Ecosystem](evidences/lo3/docker-containerization/lo3-docker-containerization.md)
* Constructed a dual-job GitHub Actions CI pipeline executing 6 parallel backend matrix runners (88 pytest tests + Docker image builds) and a Node 22 frontend verification runner (ESLint, 46 Vitest tests, Vite bundle typechecks), delivering 134 continuous automated tests to eliminate contract regressions before merging @[Continuous Integration Pipeline](evidences/lo3/continuous-integration/lo3-continuous-integration-pipeline.md)
* Implemented an automated Prometheus and Grafana distributed observability stack with zero-dependency Python process telemetry, dedicated async worker socket exporters, and declarative dashboard provisioning as code, empirically proving the ~3.4x memory overhead between Vanilla Saga and Temporal orchestration @[Distributed Observability: Prometheus & Grafana Metric Telemetry](evidences/lo3/prometheus-grafana-monitoring/lo3-prometheus-grafana-monitoring.md)

#### Professional Standard / Advising (LO4) — HBO-i: Advising (Level 3–4)

* Authored an empirical Architectural Decision Record (ADR) benchmarking Vanilla Saga vs. Temporal across 7 technical criteria, quantifying the ~10x «infrastructure tax» (~24MB vs ~240MB RAM) against the business risk of orphaned holds, and formulating an actionable «When to Choose What» decision tree for distributed architectures @[Architectural Decision Record](evidences/lo4/adr-orchestrator-selection/lo4-architectural-decision-record.md)

#### Personal Leadership (LO5) — HBO-i: Personal Leadership (Level 3)

* Facilitated a technical peer review session (Nov 9, 2026), evaluated critical feedback regarding multi-container footprint, incorporated resource metrics into the ADR, and formulated an aligned scope extension proposal for teacher consultation within the strict 38-hour PDP budget @[Peer Knowledge Sharing & Technical Feedback Reflection](evidences/lo5/peer-knowledge-sharing/lo5-peer-feedback-and-reflection.md)
* Produced a 3-minute technical pitch video and live demo; overcame illness by scripting the technical narrative and utilizing AI voiceover tools to deliver the pitch on schedule without delaying group review milestones @[Peer Knowledge Sharing Video](evidences/lo5/peer-knowledge-sharing/lo5-peer-feedback-and-reflection.md)

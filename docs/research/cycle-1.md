# Cycle 1: Research & Problem Scoping

> **Experiment:** Distributed Transaction Reliability & Workflow Orchestration (Layover)  
> **Cycle:** 1 of 5  
> **Status:** Draft / In Progress  
> **Deliverable:** Research summary, failure scenario matrix, test hypotheses, and consistency quality metrics.  
> **Learning Outcomes:** LO1 (Software Engineering), LO2 (Software Quality)

---

## 1. Executive Summary & Objectives

<!-- Briefly summarize the goal of this research cycle: scoping how partial failures break distributed workflows and establishing the empirical framework before building microservices in Cycle 2. -->

- **Core Goal:**
- **Key Deliverables:**
- **Time Allocation:** ~6 hours

---

## 2. Theoretical Foundations

### 2.1 ACID vs. BASE in Distributed Systems

<!-- Compare single-database transaction guarantees (ACID) against distributed eventual consistency (BASE). -->

| Dimension | ACID (Single Monolith DB) | BASE (Microservices Architecture) |
| :--- | :--- | :--- |
| **Atomicity** | | |
| **Consistency** | | |
| **Isolation** | | |
| **Durability** | | |
| **Availability** | | |

### 2.2 Two-Phase Commit (2PC) vs. The Saga Pattern

<!-- Contrast 2PC (blocking, synchronous coordinator) with the Saga pattern (compensating transactions). Explain why 2PC is poorly suited for autonomous microservices over HTTP. -->

- **Two-Phase Commit (2PC) Limitations:**

- **The Saga Pattern:**
  - Forward Actions:
  - Compensating Actions (Rollbacks):

### 2.3 Orchestration vs. Choreography

<!-- Compare event-driven choreography against centralized orchestration. Detail why an orchestrator was chosen for this experiment. -->

- **Choreography:**
- **Orchestration:**
- **Decision Rationale:**

### 2.4 Durable Execution & Temporal Architecture

<!-- Explain how Temporal achieves durable execution (event history, deterministic workflow replay, activity retries). -->

- **Temporal Workflow Execution Model:**
- **Deterministic Replay & Event History:**
- **Activities vs. Workflows:**
- **Compensating Activities on Failure:**

---

## 3. Research Questions & Hypotheses

### 3.1 Research Questions (RQs)

- **RQ1:**
- **RQ2:**
- **RQ3:**

### 3.2 Formal Hypotheses

- **$H_1$ (Data Consistency):**
- **$H_2$ (Recovery Overhead):**
- **$H_3$ (Code Complexity & Maintainability):**

---

## 4. Failure Scenario Matrix

The experiment tests multi-step bookings across three independent services (`Flight` :8001, `Hotel` :8002, `Payment` :8003).

| ID | Trigger Point | Injected Failure | Naive Baseline Expected Outcome | Temporal Saga Expected Outcome |
| :--- | :--- | :--- | :--- | :--- |
| **SC-01** | Post-Flight Reserve | Service crash / HTTP drop before Hotel call | Orphaned flight reservation | Automated compensation / cancellation |
| **SC-02** | Hotel Call | HTTP 500 / Network Timeout | | |
| **SC-03** | Post-Hotel Reserve | Hard crash before Payment call | Orphaned flight & hotel holds | Compensating cancellation of both |
| **SC-04** | Payment Call | Insufficient funds / Card rejected (Business Error) | | Rollback flight & hotel |
| **SC-05** | Mid-Payment | Process terminates during charge | Inconsistent payment record | Activity retry or manual reconciliation |

### Detailed Failure Walkthroughs

#### Scenario SC-01: Crash After Flight Reservation

- **Flow:** `POST /flight/reserve` succeeds $\rightarrow$ coordinator process terminates before `POST /hotel/reserve`.
- **Expected Database State (Naive):**
  - `flight.db`: `RESERVED`
  - `hotel.db`: No record
  - `payment.db`: No record
- **Expected Database State (Temporal):**
  - Workflow resumes or executes `cancel_flight` compensation on timeout.
  - Final state: `flight.db` marked `CANCELLED`.

#### Scenario SC-03: Crash After Hotel Reservation (Pre-Payment)

- **Flow:** `POST /flight/reserve` succeeds $\rightarrow$ `POST /hotel/reserve` succeeds $\rightarrow$ crash before `/payment/charge`.
- **Expected Database State (Naive):**
- **Expected Database State (Temporal):**

#### Scenario SC-04: Payment Rejection (Explicit Failure)

- **Flow:** Flight & Hotel reserved $\rightarrow$ Payment returns 402/400 (Payment Declined).
- **Expected Database State (Naive):**
- **Expected Database State (Temporal):**

---

## 5. Measurable Quality & Consistency Metrics

Before running experiments in Cycles 3, 4, and 5, define objective formulas and metrics:

### 5.1 Consistency Rate ($C_r$)

A transaction is considered in a **clean state** if and only if it is either 100% completed or 100% compensated (all holds released).

$$\text{Consistency Rate } (C_r) = \frac{N_{\text{clean}}}{N_{\text{total}}} \times 100\%$$

- **Clean States:**
  - `SUCCESS`: Flight `CONFIRMED`, Hotel `CONFIRMED`, Payment `PAID`.
  - `ABORTED`: Flight `CANCELLED`, Hotel `CANCELLED`, Payment `REFUNDED` (or not created).
- **Dirty / Zombie States:**
  - Any reservation held (`RESERVED`) without successful payment or completed cancellation.

### 5.2 Recovery Time ($T_r$)

- **Definition:** Elapsed time from restarting crashed services until all databases reflect a terminal clean state (`CONFIRMED` or `CANCELLED`).
- **Measurement Methodology:**

### 5.3 Error-Handling & Maintenance Complexity

- **Lines of Error-Handling Code (LoC):** Try/except blocks, manual rollback calls, state cleanup logic.
- **Cyclomatic Complexity:** Number of independent execution branches needed to handle partial failure in the coordinator.
- **Cognitive Overhead:** Qualitative assessment of understanding failure pathways.

---

## 6. Data Consistency Audit Checklist

Post-test verification checklist to inspect SQLite databases:

- [ ] **Flight Database (`flight.db`):**
  - Check reservation status (`RESERVED`, `CONFIRMED`, `CANCELLED`).
  - Verify seat hold timestamps and expiration.
- [ ] **Hotel Database (`hotel.db`):**
  - Check room booking status (`RESERVED`, `CONFIRMED`, `CANCELLED`).
  - Verify room availability count match.
- [ ] **Payment Database (`payment.db`):**
  - Verify payment status (`PENDING`, `COMPLETED`, `REFUNDED`, `FAILED`).
  - Verify transaction ID reference links to booking ID.

---

## 7. Next Steps & Transition to Cycle 2

- Review failure scenarios against FastAPI service designs.
- Implement isolated SQLite databases and FastAPI endpoints in Cycle 2.
- Set up automated pytest harness with `httpx.AsyncClient`.

---

## 8. References & Literature

1. Garcia-Molina, H., & Salem, K. (1987). *Sagas*. ACM SIGMOD Record.
2. Temporal Documentation: [https://docs.temporal.io](https://docs.temporal.io)
3. Newman, S. (2021). *Building Microservices* (2nd ed.). O'Reilly Media.

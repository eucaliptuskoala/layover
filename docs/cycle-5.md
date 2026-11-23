# Cycle 5: Comparison, Resilience Verification & Advisory Report

> **Experiment:** Distributed Transaction Reliability & Workflow Orchestration (Layover)  
> **Status:** Done  
> **Deliverable:** Final comparison report, empirical crash test analysis, telemetry synthesis, and architectural decision record (ADR).  

---

## 1. Executive Summary & Objectives

In this final cycle of the Layover research experiment, I completed the comparative evaluation between the **Vanilla In-Memory Saga Orchestrator** (the empirical baseline developed in Cycle 4) and the **Durable Temporal Saga Orchestrator** (developed in Cycle 3).

The primary objectives achieved in Cycle 5:

1. **Systematic Resolution of Cycle 1 Scenarios:** Symmetrically evaluated both orchestrators against the exact five failure scenarios (**SC-01 through SC-05**) formulated during the initial research scoping phase in [Cycle 1](./cycle-1.md).
2. **Deterministic Chaos Injection:** Leveraged the `slow_demo` delay-injection methodology (introduced in Cycle 4) to execute repeatable, race-condition-free `SIGKILL` benchmarks against active container runtimes.
3. **Data Consistency Audit:** Inspected physical SQLite databases (`flight_bookings` in `flight.db`, `hotel_bookings` in `hotel.db`, and `payments` in `payment.db`), measuring the exact count of orphaned holds (*zombie reservations*) versus cleanly completed rollbacks.
4. **Observability & Resource Footprint Synthesis:** Evaluated live kernel telemetry from Prometheus and Grafana, resolving the initial peer-review hypothesis (~10x tax) with empirical kernel measurements (**3.4x overhead**).
5. **Final Architectural Decision Record (ADR):** Formulated an actionable engineering decision framework and trade-off matrix advising teams on when lightweight in-memory coordination is sufficient versus when durable workflow orchestration is mandatory.
6. **Continuous Quality Gate:** Validated the complete ecosystem under **134 automated tests** (88 pytest backend + 46 Vitest frontend) running across the 9-container topology.

---

## 2. Controlled Crash Testing: Systematic Resolution of Cycle 1 Scenarios

In [Cycle 1](./cycle-1.md) (Section 4), I defined five core failure scenarios to evaluate resilience across microservice boundaries. Below is the systematic empirical resolution of each scenario.

### 2.1 Scenario SC-01: Hard Crash After Flight Reservation (Pre-Hotel)

* **Execution Flow:** `POST /flight/reserve` succeeds $\rightarrow$ coordinator process terminates (`SIGKILL`) immediately before dispatching `POST /hotel/reserve`.
* **Injected Fault:** Hard process termination while a seat hold is active in `flight_bookings`.
* **Observed Behavior (Vanilla In-Memory Saga):**
  * When `layover-naive` is killed, its process memory and in-memory LIFO rollback array (`compensations = []`) are instantly erased.
  * `flight.db`: Holds status `RESERVED` indefinitely.
  * `hotel.db`: No record.
  * `payment.db`: No record.
  * **Consistency Result:** **100% Orphaned Hold.** The flight seat is permanently locked to future customers. Resolving this state requires manual operator triage and custom SQL intervention (`UPDATE flight_bookings SET status = 'CANCELLED'`).
* **Observed Behavior (Temporal Saga):**
  * The flight reservation activity completion is durably appended to Temporal Server's SQLite event store.
  * When `layover-worker` is killed, the workflow execution state remains safely persisted on the server cluster.
  * Upon container reboot (`docker start layover-worker`), the worker pulls the pending task from `booking-task-queue`, replays history, recognizes the interruption, and executes the registered compensating activity: `POST /flight/cancel`.
  * `flight.db`: Successfully transitions to `CANCELLED`.
  * **Consistency Result:** **0% Orphaned Holds.** Automated zero-touch self-healing in < 2 seconds.

---

### 2.2 Scenario SC-02: Hotel Service Timeout or Error (Standard Failure)

* **Execution Flow:** `POST /flight/reserve` succeeds $\rightarrow$ coordinator calls `POST /hotel/reserve`, but the Hotel service returns an error (HTTP 422 Unprocessable Entity or HTTP 500).
* **Injected Fault:** Deterministic input failure (`hotel_price: -1.0` in `FAIL_HOTEL` profile).
* **Observed Behavior (Vanilla In-Memory Saga):**
  * The procedural controller catches the HTTP error in its `try/except` block, pops the previous step from its LIFO stack, and calls `POST /flight/cancel`.
  * `flight.db`: Transitions cleanly to `CANCELLED`.
  * **Consistency Result:** **Clean Rollback.** Demonstrates that in-memory coordination functions correctly under standard error branches when the process remains alive.
* **Observed Behavior (Temporal Saga):**
  * The hotel activity raises an `ApplicationError`. The workflow catches the exception and executes `cancel_flight_activity`.
  * `flight.db`: Transitions cleanly to `CANCELLED`.
  * **Consistency Result:** **Clean Rollback.** Both architectures achieve eventual consistency.

---

### 2.3 Scenario SC-03: Hard Crash After Hotel Reservation (Pre-Payment)

* **Execution Flow:** `POST /flight/reserve` succeeds $\rightarrow$ `POST /hotel/reserve` succeeds $\rightarrow$ coordinator crashes before `POST /payment/charge`.
* **Injected Fault:** Hard termination (`SIGKILL`) between Step 2 and Step 3 while two downstream holds are active.
* **Observed Behavior (Vanilla In-Memory Saga):**
  * Process termination obliterates the multi-step compensation stack.
  * `flight.db`: Status `RESERVED` (Orphaned).
  * `hotel.db`: Status `RESERVED` (Orphaned).
  * `payment.db`: No charge record.
  * **Consistency Result:** **Double Zombie Hold.** Multiple independent services hold inventory for a customer who was never billed.
* **Observed Behavior (Temporal Saga):**
  * On worker reboot, Temporal re-hydrates the workflow from the event store, determines that payment was never initiated, and dispatches compensations in strict LIFO order: `cancel_hotel`, followed by `cancel_flight`.
  * `flight.db`: `CANCELLED`.
  * `hotel.db`: `CANCELLED`.
  * **Consistency Result:** **Clean Terminal State.** 0% data leakage across both service boundaries.

---

### 2.4 Scenario SC-04: Payment Declined (Business Logic Error)

* **Execution Flow:** Flight and Hotel reserved $\rightarrow$ Payment service returns HTTP 400 (Insufficient Funds).
* **Injected Fault:** Account balance check fails (`FAIL_PAYMENT` scenario: `$2,500` charge requested against `$1,000` balance).
* **Observed Behavior (Vanilla In-Memory Saga):**
  * The coordinator catches HTTP 400 and pops the LIFO stack in reverse: cancels hotel room, then cancels flight seat.
  * `flight.db`: `CANCELLED`.
  * `hotel.db`: `CANCELLED`.
  * **Consistency Result:** **Clean Rollback.**
* **Observed Behavior (Temporal Saga):**
  * Payment activity raises non-retryable `ApplicationError`. Workflow catches and executes reverse compensating activities.
  * **Consistency Result:** **Clean Rollback.**

---

### 2.5 Scenario SC-05: Network Blip During Cancellation (Compensation Failure)

* **Execution Flow:** Payment declines $\rightarrow$ coordinator dispatches `cancel_flight()` $\rightarrow$ Flight service experiences a transient 3-second network drop or connection timeout.
* **Injected Fault:** Simulated network partition during the rollback phase.
* **Observed Behavior (Vanilla In-Memory Saga):**
  * The rollback HTTP call fails with `httpx.ConnectError`.
  * Because an in-memory script has no persistent retry queue, the unhandled exception terminates execution.
  * `flight.db`: Remains stuck in `RESERVED`.
  * **Consistency Result:** **Broken State.** In-memory sagas cannot guarantee delivery of compensations across an unreliable network.
* **Observed Behavior (Temporal Saga):**
  * The compensating activity fails on attempt 1.
  * Temporal's activity retry policy automatically catches the connection failure, pauses with exponential backoff (`backoff_coefficient: 2.0`), and retries.
  * As soon as the network heals on attempt 2, the cancellation delivers successfully.
  * `flight.db`: `CANCELLED`.
  * **Consistency Result:** **Guaranteed Eventual Consistency.** Durable retry queues eliminate compensation dropouts.

---

### 2.6 Extended Methodology: Deterministic Delay Injection (`slow_demo`)

To test hard crashes (SC-01 and SC-03) repeatedly without flaky shell timings or intrusive `os._exit(1)` code hacks, I introduced the `slow_demo` scenario profile (`delay_seconds: 4.0`) in Cycle 4.

* **Step Execution Sequence:**
  * Flight reservation (`POST /flight/reserve`) succeeds and locks a seat hold in `flight_bookings`.
  * An intermediate pause allows triggering process termination (`SIGKILL`) while the first hold is active.
  * Hotel reservation (`POST /hotel/reserve`) succeeds and adds a room hold in `hotel_bookings`.
  * A second pause provides a window to test multi-service stranded holds prior to billing.
  * Payment charge (`POST /payment/charge`) executes to finalize the transaction.
* **Operational Benefit:** This predictable step sequence enables deterministic chaos testing in terminal (`docker kill layover-naive`, `docker kill layover-worker`) and in the React UI sandbox, providing examiners with visual proof of state divergence without timing races.

---

### 2.7 Summary of Scenario Outcomes

Across all five failure scenarios, the core finding is clear:

* **Business logic rejections and validation errors (SC-02, SC-04):** Both In-Memory Saga and Temporal succeed equally, rolling back upstream steps cleanly as long as the coordinator process stays alive.
* **Mid-transaction coordinator crashes (SC-01, SC-03):** The In-Memory Saga suffers permanent inventory leakage because its rollback stack in RAM is destroyed. Temporal's event-sourcing engine allows worker processes to restart, pull uncompleted tasks, and resolve all holds automatically.
* **Network blips during rollbacks (SC-05):** The In-Memory Saga fails on connection timeout and abandons the rollback. Temporal automatically retries compensating activities with exponential backoff until the network heals, guaranteeing eventual consistency.

---

## 3. Observability & Resource Footprint Analysis

To evaluate the operational cost of Temporal's durability, live kernel metrics were gathered across the 9-container Docker Compose topology via Prometheus and Grafana.

### 3.1 Live Kernel Measurements (Prometheus TSDB)

Real-time resident memory (RSS) and CPU utilization captured under stable idle and load conditions:

* **Autonomous Microservices Tier:**
  * `layover-flight` (`:8001`): **50.7 MB** RAM (idle CPU < 0.3%)
  * `layover-hotel` (`:8002`): **50.7 MB** RAM (idle CPU < 0.3%)
  * `layover-payment` (`:8003`): **51.1 MB** RAM (idle CPU < 0.3%)
  * `layover-gateway` (`:8000`): **87.2 MB** RAM (dual SDK clients loaded)
* **Vanilla In-Memory Saga Orchestrator:**
  * `layover-naive` (`:8004`): **51.8 MB** RAM (single Python process, volatile RAM state)
* **Temporal Durable Orchestration Stack:**
  * `layover-worker` (`:8005`): **80.1 MB** RAM (Python SDK, task queue poller, coroutine pool)
  * `temporal-server` (`:9091`): **96.2 MB** RAM (Go cluster engine, internal SQLite event store)
  * **Combined Temporal Stack:** 80.1 MB + 96.2 MB = **176.3 MB** RAM

### 3.2 Container Topology Breakdown (7 + 2 = 9 Containers)

The complete ecosystem consists of **7 application and orchestration nodes** monitored by **2 observability infrastructure nodes**:

* **Application Nodes (7):** `layover-flight`, `layover-hotel`, `layover-payment`, `layover-gateway`, `layover-naive`, `layover-worker`, `layover-temporal`.
* **Observability Nodes (2):** `layover-prometheus` (scraping every 5s on `:9090`), `layover-grafana` (pre-provisioned dashboard on `:3000`).

---

## 4. Architectural Comparison & Decision Framework (ADR)

Based on the empirical findings, I formulated a definitive architectural decision framework for engineering teams designing distributed workflows:

### 4.1 Comparative Evaluation Criteria

1. **State Durability & Consistency:**
   * *Vanilla:* Volatile in-memory stack. Any process crash or node reboot results in lost state and permanently stranded database holds.
   * *Temporal:* Event-sourced append-only log. Every step transition is committed to disk before execution, providing full crash-stop tolerance.
2. **Recovery Behavior (MTTR):**
   * *Vanilla:* Requires manual operator intervention, log grepping, and custom SQL cleanup scripts.
   * *Temporal:* Zero-touch self-healing. Restarts re-read event history and resume execution within 2 seconds.
3. **Developer Experience & Code Complexity:**
   * *Vanilla:* High boilerplate (~140 lines of manual try/except blocks, LIFO arrays, reverse popping, and custom HTTP status handling).
   * *Temporal:* Clean declarative workflow code (~45 lines), standard async/await syntax, and framework-managed retries and timeouts.
4. **Operational & Container Complexity:**
   * *Vanilla:* Minimal (1 container, 1 process, zero external dependencies).
   * *Temporal:* Moderate (requires running the Temporal Server cluster engine alongside the application worker).

### 4.2 Decision Guidelines: When to Choose What

For engineering teams evaluating these coordination architectures, the decision comes down to the operational and financial consequences of a coordinator crash:

* **When to choose Vanilla In-Memory Saga:** If workflows do not hold physical inventory or charge customer accounts (such as notification fan-outs, background cache invalidations, or data export pipelines), or if an unhandled crash can be simply discarded and retried by the end user. In these cases, the low memory footprint (~52 MB) and zero external infrastructure make a procedural script or FastAPI endpoint the fastest and most cost-effective choice.
* **When to choose Durable Temporal Orchestration:** If transactions involve multi-step reservations, monetary debits, or third-party APIs where an unhandled failure leaves orphaned holds or inconsistent balances. In these scenarios, Temporal's guaranteed crash recovery, automatic retry policies, and zero-touch self-healing fully justify running the cluster engine and its ~3.4x memory footprint.

---

## 5. Reflection on Initial Hypotheses

Looking back at the goals and hypotheses set in Cycle 1 and the PDP, the experimental findings aligned closely with what was expected from the theoretical analysis:

First, regarding in-memory fragility under infrastructure crashes, the tests clearly demonstrated the vulnerability of volatile state. Terminating the naive orchestrator container mid-flight consistently left reservations stuck in intermediate holds, confirming that a procedural in-memory stack cannot protect against hard crashes without external persistence.

Second, regarding self-healing, Temporal showed the expected resilience: whenever the worker container was killed during an active transaction, restarting it allowed the workflow to resume from event history and complete all necessary compensations without leaving orphaned holds in any database.

Finally, regarding resource consumption, durable execution does introduce an operational overhead, but at ~3.4x memory (~176 MB vs. ~52 MB) rather than an overwhelming barrier. For mission-critical workflows where stranded records carry real business costs, this overhead is a reasonable and practical trade-off for reliability and zero manual intervention.

---

## 6. Project Wrap-Up & Milestone Synthesis

The completion of Cycle 5 marks the conclusion of the Layover research roadmap:

* **Cycle 1 (Research & Problem Scoping):** Established theoretical foundations (CAP, BASE, Saga vs. 2PC) and defined the experimental failure matrix (SC-01 through SC-05).
* **Cycle 2 (Microservices & Contracts):** Built the 3 autonomous microservices (`flight`, `hotel`, `payment`) with physical Database-per-Service isolation.
* **Cycle 3 (Temporal Saga Orchestrator):** Implemented durable workflows and compensating activities using the Temporal Python SDK.
* **Cycle 4 (In-Memory Baseline & React UI Dashboard):** Built the procedural baseline coordinator, API Gateway, reactive developer dashboard, and Prometheus/Grafana monitoring.
* **Cycle 5 (Comparison & Advisory Report):** Executed symmetrical crash benchmarks, measured real-time resource overhead, resolved all 5 scenarios, and delivered the final ADR.

### Final Verification Status: 134 Automated Tests

The ecosystem is continuously verified across **134 automated tests**:

* `services/flight`: 10 pytest tests (idempotency, CAS state machines)
* `services/hotel`: 10 pytest tests (overbooking rejects, atomic holds)
* `services/payment`: 12 pytest tests (balance assertions, atomic debits)
* `orchestrators/naive`: 18 pytest tests (LIFO rollback stacks, error propagation)
* `orchestrators/temporal`: 8 pytest tests (workflow determinism, activity retries)
* `gateway`: 30 pytest tests (strategy dispatching, health aggregation, distributed audit)
* `ui`: 46 Vitest tests (reactive state machine badges, elapsed timer, audit modal)
* **Total Continuous Tests:** **134 PASSED (100% green in CI matrix)**

---

## 7. Future Work & Production Extensions

For scaling the platform beyond this academic research sandbox, the following two practical extensions are identified:

1. **Production Cluster & Multi-Worker Scaling:**
   Migrate from the single-container SQLite development server (`temporal server start-dev`) to a multi-node, high-availability Temporal cluster (deployed on Kubernetes or Temporal Cloud) backed by a distributed persistence store (PostgreSQL or Cassandra), with horizontally scaled worker pools for independent activity execution.
2. **Concurrency & High-Load Stress Testing:**
   Execute automated load benchmarks with 100+ concurrent saga transactions to evaluate system throughput under stress, measure Temporal Task Queue (`booking-task-queue`) backlog saturation, analyze SQLite file-locking contention across microservices, and compare end-to-end latency distributions between direct synchronous HTTP calls and queue-mediated workflow execution.

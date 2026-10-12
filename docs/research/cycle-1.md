# Cycle 1: Research & Problem Scoping

> **Experiment:** Distributed Transaction Reliability & Workflow Orchestration (Layover)  
> **Status:** Done  
> **Deliverable:** Research summary, failure scenario matrix, test hypotheses, and consistency quality metrics.  

---

## 1. Executive Summary & Objectives

- **Core Goal:** Research and understand how distributed systems work, how failures are handled, and establish an empirical framework for evaluating different failure handling strategies.

---

## 2. Theoretical Foundations

### 2.1 Monolith vs Micro-services vs Distributed Monolith

Software architectures can be categorized by how components communicate and deploy:

- **Monolith:** All business domains (Flights, Hotels, Payments) run inside a single process and communicate via in-memory function calls. Memory access is fast (nanoseconds), perfectly reliable, and shares a single database where ACID transactions guarantee that any error triggers an immediate `ROLLBACK`. The trade-off is organizational scaling: tight coupling makes independent deployments and scaling difficult.
- **Microservices:** Business domains are divided into small, autonomous services that communicate over a network (HTTP/REST or gRPC). Each service has its own codebase, runtime, and deployment lifecycle. The benefit is independent deployment, clear ownership, and fault isolation. The cost is that every cross-boundary call must traverse an unreliable network, introducing latency, timeouts, and partial failure.
- **Distributed Monolith (The Anti-Pattern):** Services are split into separate network runtimes, but remain tightly coupled through shared databases, shared code libraries, or synchronous cascade dependencies. This architecture suffers from all the operational complexity and network latency of microservices, without gaining any independence or autonomy.

> **Design Rule for Layover:** Each service (`Flight`, `Hotel`, `Payment`) must run as an entirely autonomous process. They must never share runtime memory or internal code dependencies.

---

### 2.2 Databases in Distributed Systems

In a monolithic architecture, multiple domains share a single relational database schema. When a flight is booked and a hotel reserved, a single SQL transaction commits both rows simultaneously. If one fails, the database engine aborts both.

In microservices, the **Database-per-Service** pattern is mandatory:

- Each service owns a private database that no other service can access directly.
- All data access and mutations must pass through the service's public API.
- Cross-database SQL `JOIN` queries become impossible.

To retrieve and view data spanning multiple domains, two primary patterns exist:

1. **API Composition:** An aggregator component queries the individual services over HTTP and stitches the results together in memory.
2. **Command Query Responsibility Segregation (CQRS):** Read views are separated from write models, using event subscribers to maintain denormalized read-only views across services.

> **Design Rule for Layover:** True database isolation. Flight maintains `flight.db`, Hotel maintains `hotel.db`, and Payment maintains `payment.db`. To query booking status across all three services, the dashboard coordinator uses API Composition.

---

### 2.3 CAP Theorem

The CAP Theorem (Brewer's Theorem) states that any distributed data store can guarantee at most two out of three properties simultaneously:

- **Consistency (C):** Every read receives the most recent write or an error (linearizability).
- **Availability (A):** Every non-failing node returns a non-error response for every request, without guarantee that it contains the most recent write.
- **Partition Tolerance (P):** The system continues to operate despite an arbitrary number of messages being dropped or delayed by the network between nodes.

In any networked distributed system, network partitions (P) are an unavoidable physical reality: servers crash, routers hiccup, and connections time out. Therefore, architects cannot choose "CA" — the only real choice is between **CP** and **AP** during a partition:

- **CP (Consistency over Availability):** The system rejects requests or halts execution until the network heals, ensuring no stale or conflicting data is recorded.
- **AP (Availability over Consistency):** The system continues accepting requests on available nodes, sacrificing immediate consistency and reconciling data later (Eventual Consistency).

> **Design Rule for Layover:** Over an HTTP network, we accept that network partitions (P) occur. Rather than halting the entire application when one downstream service times out (CP), we design for Availability (AP) and use compensation logic to achieve eventual consistency.

### 2.4 ACID vs. BASE in Distributed Systems

Single-database systems rely on **ACID** transactions:

- **Atomicity:** All statements in a transaction succeed, or the entire transaction is rolled back.
- **Consistency:** Transactions move the database from one valid state to another, enforcing constraints.
- **Isolation:** Concurrent transactions cannot see each other's uncommitted intermediate states.
- **Durability:** Once committed, changes survive system crashes via write-ahead logging.

Across distributed microservices with isolated databases, global ACID is impossible without blocking distributed locks. Instead, distributed systems operate under the **BASE** model:

- **Basically Available:** The system prioritizes availability; individual services respond even if other parts of the workflow are degraded.
- **Soft State:** Data values may change over time without user interaction because the system is still reconciling intermediate steps (for example, a flight status may sit in `RESERVED` while payment is still processing).
- **Eventual Consistency:** Given enough time without new failures, all participating databases converge to a consistent, agreed-upon terminal state.

> **Design Rule for Layover:** Reject global locks. Treat intermediate states (`RESERVED`) as first-class citizens in service schemas, and ensure the workflow engine guarantees eventual transition to terminal states (`CONFIRMED` or `CANCELLED`).

### 2.5 Two-Phase Commit (2PC) vs. The Saga Pattern

To coordinate transactions across multiple independent databases, two core patterns exist:

#### Two-Phase Commit (2PC)

A centralized transaction coordinator asks all participating databases to prepare a commit (Phase 1: Voting), and if all say yes, tells them all to commit (Phase 2: Execution).

- **Why 2PC fails in microservices:** 2PC holds synchronous database locks on all rows across the entire network duration. If the coordinator or any service crashes mid-vote, locks are held indefinitely, stalling the entire system. Furthermore, 2PC violates service autonomy by exposing low-level XA database interfaces across service boundaries.

#### The Saga Pattern

A Saga breaks a long distributed transaction into a sequence of **local transactions**:

1. Each step executes in its own service and commits immediately to its local database, releasing local locks.
2. If every step succeeds, the saga completes.
3. If a step fails, the saga executes **compensating transactions** in reverse order to undo the changes made by earlier steps.
   - Example forward action: `POST /hotel/reserve` (books a room).
   - Example compensating action: `POST /hotel/cancel` (releases the room).

Crucially, compensating actions must be **idempotent**: calling `/hotel/cancel` multiple times must produce the exact same outcome as calling it once, preventing duplicate refunds or crashes during retries.

> **Design Rule for Layover:** Every service endpoint that mutates state (`/reserve`, `/charge`) MUST provide a corresponding, idempotent compensating endpoint (`/cancel`, `/refund`) that safely undoes the operation.

### 2.6 Orchestration vs. Choreography

Sagas can be coordinated in two different styles:

#### Choreography (Decentralized / Event-Driven)

Services publish domain events to a shared message broker (e.g. RabbitMQ or Kafka), and other services listen and respond:

- Flight reserves a seat and emits `FlightReserved`.
- Hotel hears `FlightReserved`, books a room, and emits `HotelReserved`.
- Payment hears `HotelReserved` and attempts to charge the card.
- **Drawbacks:** There is no centralized place to inspect the state of a transaction. As the workflow grows, the event graph becomes tangled ("pinball machine architecture"), and tracing where a failed saga stalled requires querying multiple independent event streams.

#### Orchestration (Centralized Coordinator)

A single orchestrator component explicitly directs the workflow:

- The orchestrator calls Flight (`POST /reserve`).
- When Flight responds `200 OK`, the orchestrator calls Hotel (`POST /reserve`).
- If Hotel fails or crashes, the orchestrator directly calls Flight's compensating endpoint (`POST /cancel`).
- **Benefits:** The entire workflow state, execution timeline, and error branches are visible in one place. It is easy to reason about timeouts, retries, and rollback logic without needing an external message broker.

> **Design Rule for Layover:** Use centralized orchestration. A travel booking is an inherently sequential, linear business process where centralized visibility, explicit error handling, and visual observability are paramount.

### 2.7 Durable Execution & Temporal Architecture

Standard sequential scripts running in application memory (like planned ‹naive baseline) are ephemeral: if the server running the script restarts, crashes, or runs out of memory mid-transaction, all execution state is lost, leaving holds orphaned.

**Durable Execution** solves this by separating business logic from execution reliability:

- **Event Sourcing / Event History:** Every activity initiation, completion, timeout, and failure is recorded in an append-only event log.
- **Deterministic Replay:** If an orchestrator worker crashes mid-workflow, a new worker restarts, reads the event history, replays the workflow code deterministically, fast-forwards through already completed steps without re-executing them, and resumes execution exactly where the failure occurred.
- **Workflows vs. Activities:**
  - *Workflows:* Pure orchestration logic. Must be deterministic (no random numbers, direct system clock reads, or direct network I/O).
  - *Activities:* Non-deterministic operations that interact with the outside world (making HTTP requests to Flight, Hotel, Payment). Activities can be configured with automated retry policies, backoffs, and timeouts.

> **Design Rule for Layover:** In Temporal, the booking sequence is implemented as a deterministic `@workflow.defn`. All HTTP calls to external microservices are isolated inside `@activity.defn` functions, each paired with an explicit compensating activity registered on the workflow's rollback stack.

---

## 3. Research Questions & Hypotheses

### 3.1 Research Questions (RQs)

- **RQ1:** To what extent does a naive sequential execution leave orphaned state in microservice databases under partial failure, compared to an orchestrated Saga pattern?
- **RQ2:** What is the difference in recovery time and manual intervention required between in-process error handling and durable workflow orchestration following an unhandled coordinator crash?
- **RQ3:** What is the overhead in code complexity, cognitive load, and operational requirements when introducing Temporal compared to standard sequential scripting?

### 3.2 Formal Hypotheses

- **$H_1$ (Data Consistency):** The naive baseline will result in a consistency rate $C_r < 100\%$ under process termination (leaving orphaned holds), whereas the Temporal Saga will achieve $C_r = 100\%$ by automatically executing compensating rollbacks.
- **$H_2$ (Recovery Overhead):** The naive baseline will require manual database cleanup script intervention upon crash, whereas Temporal will automatically reconcile or resume on worker restart with zero manual intervention.
- **$H_3$ (Code Complexity & Maintainability):** Temporal reduces the lines of nested error-handling and rollback code in the coordinator, but introduces framework-specific learning curves and local infrastructure dependencies (`temporal server start-dev`).

---

## 4. Failure Scenario Walkthroughs

The experiment tests multi-step bookings across three independent services (`Flight` :8001, `Hotel` :8002, `Payment` :8003). To evaluate resilience without relying on summary tables, each failure scenario is defined by its trigger point, injected fault, and expected outcome for both implementations.

### Scenario SC-01: Crash After Flight Reservation (Pre-Hotel)

- **Execution Flow:** `POST /flight/reserve` succeeds $\rightarrow$ coordinator process crashes before calling `POST /hotel/reserve`.
- **Injected Fault:** Hard process termination (`SIGKILL` / `os._exit(1)`) immediately after the flight reservation responds.
- **Expected Database State (Naive Baseline):**
  - `flight.db`: `RESERVED` (Orphaned hold; seat locked without a completed trip).
  - `hotel.db`: No record.
  - `payment.db`: No record.
  - *Outcome:* Dirty zombie state. The seat is permanently lost to inventory until manual database intervention.
- **Expected Database State (Temporal Saga):**
  - Upon worker recovery or activity timeout, Temporal detects the incomplete workflow.
  - The workflow executes the compensating action: `POST /flight/cancel`.
  - `flight.db`: `CANCELLED`.
  - *Outcome:* Clean terminal state ($C_r = 100\%$).

### Scenario SC-02: Hotel Service Unreachable / Network Timeout

- **Execution Flow:** `POST /flight/reserve` succeeds $\rightarrow$ coordinator attempts `POST /hotel/reserve`, but the hotel service times out or returns HTTP 500.
- **Injected Fault:** Hotel service delays response past client timeout (`asyncio.sleep(60)`) or returns 500 Internal Server Error.
- **Expected Database State (Naive Baseline):**
  - Coordinator enters in-memory `except` block. If it executes `cancel_flight()`, consistency is preserved. However, if the coordinator process crashes during this error handler, the flight hold remains permanently orphaned.
- **Expected Database State (Temporal Saga):**
  - Temporal catches the activity timeout, retries according to policy, and upon exhausting retries, triggers the rollback stack, calling `cancel_flight`.
  - `flight.db`: `CANCELLED`.
  - `hotel.db`: No record (or cancelled).
  - *Outcome:* Reliable automatic rollback guaranteed by durable event history.

### Scenario SC-03: Crash After Hotel Reservation (Pre-Payment)

- **Execution Flow:** `POST /flight/reserve` succeeds $\rightarrow$ `POST /hotel/reserve` succeeds $\rightarrow$ coordinator process crashes before calling `POST /payment/charge`.
- **Injected Fault:** Simulated crash between Step 2 and Step 3.
- **Expected Database State (Naive Baseline):**
  - `flight.db`: `RESERVED`.
  - `hotel.db`: `RESERVED`.
  - `payment.db`: No record.
  - *Outcome:* Double-orphaned zombie state. Two separate businesses hold inventory for a customer who was never charged.
- **Expected Database State (Temporal Saga):**
  - On restart, Temporal replays history, realizes flight and hotel succeeded, but payment was never initiated.
  - It triggers compensation in reverse order: `cancel_hotel`, then `cancel_flight`.
  - Both databases record `CANCELLED`.
  - *Outcome:* Clean terminal state.

### Scenario SC-04: Payment Declined (Business Error)

- **Execution Flow:** Flight and Hotel reservations succeed $\rightarrow$ Payment service responds with HTTP 402 (Insufficient Funds / Card Declined).
- **Injected Fault:** Deterministic business error returned by the payment service.
- **Expected Database State (Naive Baseline):**
  - Sequential controller catches HTTP 402 and attempts sequential cancellations. Vulnerable to mid-rollback crashes.
- **Expected Database State (Temporal Saga):**
  - Payment activity throws non-retryable `ApplicationError`.
  - Temporal executes the registered compensation stack, ensuring both hotel and flight holds are released.
  - *Outcome:* Clean abort and full inventory release.

### Scenario SC-05: Crash Mid-Payment Charge

- **Execution Flow:** Flight and Hotel reserved $\rightarrow$ `POST /payment/charge` initiated $\rightarrow$ process terminates while payment record is writing.
- **Injected Fault:** Process terminates during credit card processing.
- **Expected Database State (Naive Baseline):**
  - Ambiguous / in-doubt state. Flight and hotel held, payment status unknown. Risk of double-charging if the user clicks "Retry".
- **Expected Database State (Temporal Saga):**
  - Temporal checks activity status using the unique `idempotency_key` (linked to `booking_id`).
  - If payment completed before crash: workflow continues to confirm flight and hotel.
  - If payment failed: workflow cleanly compensates flight and hotel.
  - *Outcome:* Zero duplicate charges; consistent state.

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
- **Measurement Methodology:** Measure the timestamp delta from service reboot to the last recorded compensation or confirmation in SQLite audit logs.

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

## 7. References & Literature

1. Josh Clemm. (Brief History of Scaling Uber). (2024, March) <https://highscalability.com/brief-history-of-scaling-uber/>
2. Teddy Morin. (Understand the Difference Between Monolith, MicroServices, and Distributed Monolith). (2023, August). <https://dev.to/morintd/understand-the-difference-between-monolith-microservices-and-distributed-monolith-39kb>
3. Chris Richardson. (Pattern: Database per service). (n.d.). <https://microservices.io/patterns/data/database-per-service.html>
4. Chris Richardson. (Pattern: Saga). (n.d.). <https://microservices.io/patterns/data/saga.html>
5. Kiran Puli. (The CAP Theorem: Understanding the Trade-offs in Distributed Systems). (2025, May). <https://medium.com/@kiranpuli/the-cap-theorem-understanding-the-trade-offs-in-distributed-systems-6d39fb871fc9>
6. Chris Richardson. (Pattern: Command Query Responsibility Segregation (CQRS)). (n.d.). <https://microservices.io/patterns/data/cqrs.html>
7. Chris Richardson. (Pattern: API Composition). (n.d.). <https://microservices.io/patterns/data/api-composition.html>
8. Amazon Web Services. (What’s the Difference Between an ACID and a BASE Database?) (n.d.). <https://aws.amazon.com/compare/the-difference-between-acid-and-base-database/>
9. Geeks for Geeks. (Orchestration vs. Choreography in Microservices). (2025, July). <https://www.geeksforgeeks.org/system-design/orchestration-vs-choreography/>
10. Tom Wheeler. (The definitive guide to Durable Execution). (2025, May). <https://temporal.io/blog/what-is-durable-execution>

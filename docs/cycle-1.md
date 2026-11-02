# Cycle 1: Research & Problem Scoping

> **Experiment:** Distributed Transaction Reliability & Workflow Orchestration (Layover)  
> **Status:** Done  
> **Deliverable:** Research summary, failure scenario matrix, test hypotheses, and consistency quality metrics.  

---

## 1. Executive Summary & Objectives

- **Core Goal:** Understand why multi-service transactions break during partial failures, and define the test scenarios to compare in-memory rollbacks against Temporal.

---

## 2. Theoretical Foundations

### 2.1 Monolith vs Micro-services vs Distributed Monolith

Software architectures can be categorized by how components communicate and deploy:

- **Monolith:** All business domains (Flights, Hotels, Payments) run inside a single process and communicate via in-memory function calls. Memory access is fast (nanoseconds), perfectly reliable, and shares a single database where ACID transactions guarantee that any error triggers an immediate `ROLLBACK`. The trade-off is organizational scaling: tight coupling makes independent deployments and scaling difficult.
- **Microservices:** Business domains are divided into small, autonomous services that communicate over a network (HTTP/REST or gRPC). Each service has its own codebase, runtime, and deployment lifecycle. The benefit is independent deployment, clear ownership, and fault isolation. The cost is that every cross-boundary call must traverse an unreliable network, introducing latency, timeouts, and partial failure.
- **Distributed Monolith (The Anti-Pattern):** Services are split into separate network runtimes, but remain tightly coupled through shared databases, shared code libraries, or synchronous cascade dependencies. This architecture suffers from all the operational complexity and network latency of microservices, without gaining any independence or autonomy.

> **Architectural Takeaway:** To avoid the distributed monolith trap, I isolate each domain (`Flight`, `Hotel`, `Payment`) into its own autonomous process with zero shared runtime memory or internal code dependencies.

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

> **Architectural Takeaway:** Because cross-service SQL joins violate service boundaries, I enforce database-per-service isolation (`flight.db`, `hotel.db`, `payment.db`). To retrieve combined booking states for the client, I use API Composition in the coordinator.

---

### 2.3 CAP Theorem

The CAP Theorem (Brewer's Theorem) states that any distributed data store can guarantee at most two out of three properties simultaneously:

- **Consistency (C):** Every read receives the most recent write or an error (linearizability).
- **Availability (A):** Every non-failing node returns a non-error response for every request, without guarantee that it contains the most recent write.
- **Partition Tolerance (P):** The system continues to operate despite an arbitrary number of messages being dropped or delayed by the network between nodes.

In any networked distributed system, network partitions (P) are an unavoidable physical reality: servers crash, routers hiccup, and connections time out. Therefore, architects cannot choose "CA" — the only real choice is between **CP** and **AP** during a partition:

- **CP (Consistency over Availability):** The system rejects requests or halts execution until the network heals, ensuring no stale or conflicting data is recorded.
- **AP (Availability over Consistency):** The system continues accepting requests on available nodes, sacrificing immediate consistency and reconciling data later (Eventual Consistency).

> **Architectural Takeaway:** Since network partitions (P) are an unavoidable physical reality over HTTP, I choose an AP design over CP. Instead of halting the whole system during downstream timeouts, I prioritize availability and rely on compensating transactions to achieve eventual consistency.

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

> **Architectural Takeaway:** Because global distributed locks are impractical across microservices, I embrace BASE semantics. Intermediate states (`RESERVED`) are treated as first-class statuses in each service's schema, and the workflow coordinator is responsible for driving them to a final terminal state (`CONFIRMED` or `CANCELLED`).

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

> **Architectural Takeaway:** Because Two-Phase Commit is too heavy and locking for microservices, I adopt the Saga pattern. This requires that every mutating forward endpoint (`/reserve`, `/charge`) has a matching, idempotent compensating endpoint (`/cancel`, `/refund`) to allow safe rollbacks under failure.

### 2.6 Orchestration vs. Choreography

Sagas can be coordinated in two different styles:

#### Choreography (Decentralized / Event-Driven)

Services publish domain events to a shared message broker (such as RabbitMQ or Kafka), and other services subscribe and react independently:

- Flight reserves a seat and publishes `FlightReserved`.
- Hotel consumes `FlightReserved`, books a room, and publishes `HotelReserved`.
- Payment consumes `HotelReserved` and charges the customer.
- **Strengths:**
  - **Loose coupling:** Services do not need to know about each other or a central coordinator; they only interact with message contracts.
  - **High throughput:** No single coordinator bottleneck; ideal for event-driven broadcast workflows (e.g. sending confirmation emails, triggering analytics).
  - **No single point of coordinator failure:** If one worker fails, others continue processing the queue independently.
- **Trade-offs & Challenges:**
  - **Distributed visibility:** There is no single place to query the current state of an in-flight booking. Understanding where a transaction stalled requires correlating logs across multiple independent event streams.
  - **Complex rollback coordination:** If payment fails, compensation events (`PaymentFailed` $\rightarrow$ `CancelHotel` $\rightarrow$ `CancelFlight`) must propagate across services. As business workflows grow, the event graph can become tangled and difficult to debug ("pinball machine architecture").

#### Orchestration (Centralized Coordinator)

A dedicated coordinator component explicitly invokes each service in a defined sequence via direct requests (HTTP or gRPC):

- The coordinator calls Flight (`POST /reserve`).
- Upon success, the coordinator calls Hotel (`POST /reserve`).
- If any step fails, the coordinator explicitly executes the compensating rollback calls (e.g. `POST /flight/cancel`).
- **Strengths:**
  - **Centralized state & visibility:** The complete state machine, step sequence, and error branches live in one place. Clients can query the coordinator for immediate booking status.
  - **Straightforward linear logic:** Easier to implement, trace, and reason about timeouts, conditional branches, and rollback order.
- **Trade-offs & Challenges:**
  - **Single point of failure / bottleneck:** If the coordinator goes down or becomes overloaded, new bookings stall unless the coordinator is designed for high availability.
  - **Tighter coupling:** The coordinator must know the interfaces and endpoints of all participating microservices.

> **Architectural Takeaway:** While choreography is effective for decoupled event broadcasting, a travel booking is an end-user synchronous request-response flow. I choose centralized orchestration because having an explicit coordinator makes the sequence predictable, errors immediately visible to the client, and recovery behavior straightforward to test and compare.

---

### 2.7 In-Memory Saga vs. Durable Execution (Temporal)

Once orchestration is chosen, the critical engineering question becomes: *How is the coordinator implemented?*

1. **In-Memory Saga (Ad-Hoc / Procedural Rollbacks):**
   A standard application script manages the sequence using local memory and `try/except` blocks:
   - As each step succeeds, its compensating action is pushed onto an in-memory LIFO stack.

   - If a downstream service rejects a request (e.g. card declined), the `except` block iterates through the stack and calls `/cancel`.
   - **The Critical Vulnerability:** All state exists solely in the process memory of the coordinator. If the coordinator process crashes (`kill -9`, server reboot, out-of-memory error) mid-transaction, the in-memory stack is wiped out instantly. Any reservations already made remain permanently held in downstream databases. Furthermore, if a network timeout occurs during a rollback call, an in-memory script has no persistent retry queue to guarantee delivery.

2. **Durable Saga (Temporal Orchestration):**
   A workflow orchestrator backed by a persistent event-sourcing engine:
   - **Event History:** Every step initiation, success, failure, and timer is persisted to an append-only event log.
   - **Deterministic Replay:** If the coordinator worker crashes mid-booking, a new worker restarts, reads the event history, replays the workflow state deterministically, and resumes execution exactly where it left off.
   - **Durable Retries:** Both forward actions and compensating actions are executed as isolated activities with persistent retry policies and exponential backoff, ensuring network blips during rollbacks do not cause data loss.

---

## 3. Research Questions & Hypotheses

### 3.1 Research Questions (RQs)

- **RQ1 (Data Consistency under Failure):** In which failure scenarios does an in-memory Saga coordinator successfully maintain database consistency, and under what specific conditions (process crash vs. network timeout) does it leave orphaned reservations behind?
- **RQ2 (Recovery & Self-Healing):** How do the two approaches recover after a coordinator crash or service outage? Does the system heal automatically upon restart, or does it require manual database inspection and cleanup?
- **RQ3 (Engineering & Operational Trade-off):** What is the practical trade-off between the code simplicity of an in-memory script and the operational overhead of running a durable workflow engine (Temporal)?

### 3.2 Hypotheses

- **Hypothesis 1 (Business Errors vs. Infrastructure Crashes):**
  - Under predictable **business rejections** (e.g. hotel overbooked, card declined), both the In-Memory Saga and Temporal will successfully execute compensating rollbacks and release held inventory.
  - Under **infrastructure failures** (coordinator process termination mid-flight or network timeouts during cancellation), the In-Memory Saga will lose its execution state and leave orphaned holds in SQLite, whereas Temporal will achieve eventual consistency by replaying event history and retrying compensations.
- **Hypothesis 2 (Operational Recovery Effort):**
  - When the In-Memory coordinator crashes, fixing orphaned database records will require manual intervention (writing and executing SQL cleanup scripts).
  - When the Temporal worker crashes and restarts, it will resume and complete pending workflows automatically without human intervention.
- **Hypothesis 3 (Complexity vs. Guarantees):**
  - An in-memory script is fast to write and requires zero extra infrastructure, making it attractive for simple prototypes. However, as rollback logic, retries, and timeout branches accumulate, the code becomes fragile. Temporal introduces a steeper learning curve and operational dependencies, but shifts the burden of state management and retries from application code to the platform.

---

## 4. Failure Scenario Walkthroughs

The experiment tests multi-step bookings across three independent services (`Flight` :8001, `Hotel` :8002, `Payment` :8003). To evaluate resilience, each scenario defines the trigger point, injected fault, and expected outcome for both implementations.

### Scenario SC-01: Hard Crash After Flight Reservation (Pre-Hotel)

- **Execution Flow:** `POST /flight/reserve` succeeds $\rightarrow$ coordinator process crashes before calling `POST /hotel/reserve`.
- **Injected Fault:** Hard process termination (`SIGKILL`) immediately after the flight reservation responds.
- **Expected Outcome (In-Memory Saga):**
  - Process memory is wiped out; the rollback stack disappears.
  - `flight.db`: `RESERVED` (Orphaned hold; seat locked without a completed trip or payment).
  - `hotel.db`: No record.
  - `payment.db`: No record.
  - *Result:* Inconsistent zombie state. The seat is permanently lost to inventory until someone manually cleans up the database.
- **Expected Outcome (Temporal Saga):**
  - The workflow execution is safely recorded in Temporal Server's event log.
  - When a worker restarts (or times out), Temporal detects the incomplete workflow and executes the registered compensating activity: `POST /flight/cancel`.
  - `flight.db`: Transitions to `CANCELLED`.
  - *Result:* Clean, automatic rollback to a consistent state.

### Scenario SC-02: Hotel Service Timeout or Error (Standard Failure)

- **Execution Flow:** `POST /flight/reserve` succeeds $\rightarrow$ coordinator attempts `POST /hotel/reserve`, but the hotel service times out or returns HTTP 500.
- **Injected Fault:** Hotel service delays response past client timeout or returns an error.
- **Expected Outcome (In-Memory Saga):**
  - The coordinator catches the exception in its `except` block, iterates through its rollback stack, and calls `cancel_flight()`.
  - If the flight service is healthy and the coordinator stays alive, the flight hold is successfully cancelled.
  - *Result:* Consistent state (demonstrating that In-Memory Saga works fine for standard, un-crashed error branches).
- **Expected Outcome (Temporal Saga):**
  - Temporal catches the activity timeout, retries according to policy, and upon exhausting retries, triggers the rollback stack calling `cancel_flight`.
  - `flight.db`: `CANCELLED`.
  - *Result:* Consistent state, with automatic retries before aborting.

### Scenario SC-03: Hard Crash After Hotel Reservation (Pre-Payment)

- **Execution Flow:** `POST /flight/reserve` succeeds $\rightarrow$ `POST /hotel/reserve` succeeds $\rightarrow$ coordinator process terminates before calling `POST /payment/charge`.
- **Injected Fault:** Process termination between Step 2 and Step 3.
- **Expected Outcome (In-Memory Saga):**
  - Both flight and hotel remain in `RESERVED` status.
  - *Result:* Double-orphaned state. Two separate services hold inventory for a customer who was never charged.
- **Expected Outcome (Temporal Saga):**
  - On restart, Temporal reads event history, identifies that payment was never initiated, and triggers compensation in reverse order: `cancel_hotel`, then `cancel_flight`.
  - Both databases record `CANCELLED`.
  - *Result:* Clean terminal state.

### Scenario SC-04: Payment Declined (Business Logic Error)

- **Execution Flow:** Flight and Hotel reserved $\rightarrow$ Payment service responds with HTTP 400 (Insufficient Funds).
- **Injected Fault:** Deterministic business rejection from the payment service.
- **Expected Outcome (In-Memory Saga):**
  - Coordinator catches HTTP 400 and calls `cancel_hotel` and `cancel_flight`. Both succeed.
  - *Result:* Clean cancellation.
- **Expected Outcome (Temporal Saga):**
  - Payment activity throws non-retryable `ApplicationError`. Workflow triggers the compensation stack.
  - *Result:* Clean cancellation.

### Scenario SC-05: Network Blip During Cancellation (Compensation Failure)

- **Execution Flow:** Payment fails $\rightarrow$ coordinator attempts to compensate by calling `cancel_flight()` $\rightarrow$ flight service experiences a temporary 3-second network drop.
- **Injected Fault:** Transient connection drop injected during the rollback step.
- **Expected Outcome (In-Memory Saga):**
  - The in-memory script's rollback call fails with a connection error. Because it has no persistent retry queue, the script exits with an unhandled exception.
  - `flight.db`: Remains `RESERVED` (orphaned).
  - *Result:* Broken data due to lack of durable retries.
- **Expected Outcome (Temporal Saga):**
  - The compensating activity fails on attempt 1, waits with exponential backoff, and retries on attempt 2 after the network heals.
  - `flight.db`: Successfully `CANCELLED`.
  - *Result:* Guaranteed compensation delivery.

---

## 5. Practical Evaluation Criteria

Rather than relying on abstract formulas, the experiment evaluates the two approaches using concrete, observable criteria:

### 5.1 Orphaned Reservation Count & Consistency

After each test scenario, I inspect the SQLite databases (`flight.db`, `hotel.db`, `payment.db`). A test run is considered **clean** if and only if all participating services reach an agreed-upon terminal state:

- **Clean Success:** Flight `CONFIRMED`, Hotel `CONFIRMED`, Payment `PAID`.
- **Clean Abort:** All reserved holds are transitioned to `CANCELLED` (or refund issued).
- **Orphaned / Zombie State:** Any record left in an intermediate `RESERVED` status without payment or cancellation.

I record the exact count of orphaned holds generated by each coordinator across all crash scenarios.

### 5.2 Self-Healing vs. Manual Recovery Effort

For every scenario involving a crash or transient failure:

- Does the system automatically resolve its state upon service restart?
- Or does it leave the database in an inconsistent state that requires manual operator intervention (writing and running custom SQL cleanup scripts)?

### 5.3 Implementation & Operational Footprint

I document the practical overhead of both approaches:

- **Application Code Complexity:** Number of lines of rollback code, nesting depth of `try/except` blocks, and mental overhead required to handle edge cases.
- **Operational Dependencies:** A standalone Python script (zero infrastructure) vs. running a Temporal cluster (server process, database storage, gRPC networking, and worker deployment).

---

## 6. Data Consistency Audit Checklist

Post-test verification checklist to inspect SQLite databases:

- **Flight Database (`flight.db`):**
  - Check reservation status (`RESERVED`, `CONFIRMED`, `CANCELLED`).
  - Verify seat hold timestamps and expiration.
- **Hotel Database (`hotel.db`):**
  - Check room booking status (`RESERVED`, `CONFIRMED`, `CANCELLED`).
  - Verify room availability count match.
- **Payment Database (`payment.db`):**
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

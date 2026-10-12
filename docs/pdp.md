# Personal Development Plan

## Individual — Travel Booking Microservices (Fault Tolerance & Workflow Reliability)

When building distributed systems, things fail all the time: servers crash, network requests time out, and services go down mid-transaction. I want to understand how to keep data consistent when these failures happen.

In this project, I will build a simple travel booking app with three independent microservices in Python (FastAPI), isolated SQLite databases, and a lightweight React (Vite) dashboard. Then, I will deliberately crash services halfway through a booking to compare two approaches: a standard sequential script (the naive baseline) versus a workflow orchestrator – Temporal's Python SD. I will measure which approach leaves broken data behind, how they recover, and what it takes to write and test them properly.

## What are you going to do?

I will build a small, complete booking application with three independent microservices written in Python (FastAPI), each with its own SQLite database, plus a simple frontend dashboard in React (Vite):

- **Flight Service:** Handles seat reservations (`POST /reserve`, `POST /cancel`) and writes to `flight.db`.
- **Hotel Service:** Handles room reservations (`POST /reserve`, `POST /cancel`) and writes to `hotel.db`.
- **Payment Service:** Handles payments (`POST /charge`, `POST /refund`) and writes to `payment.db`.
- **Frontend Dashboard (UI):** A single-page React (Vite) dashboard where I can trigger a booking, see real-time service statuses, and flip a switch to intentionally crash a service during the booking.

With this setup running, I will implement and test two different booking coordinators:

1. **Version A (Naive Baseline):** A standard controller that calls Flight → Hotel → Payment one after another using basic HTTP requests. If something crashes mid-way, state is left unhandled.
2. **Version B (Temporal Orchestration):** The same multi-step booking implemented as a durable Temporal workflow using the Saga pattern. If any step fails or crashes, Temporal automatically retries or triggers compensating actions (e.g., cancelling the hotel if payment fails).
3. **Controlled Crash Testing:** I will simulate a failure (e.g. killing the hotel service right after flight reservation succeeds) and inspect the three databases. I will measure:
   - **Data consistency:** How many orphaned reservations exist (e.g., seats or rooms held without payment)?
   - **Recovery behavior:** Does the system fix itself when restarted, or does it require manual database cleanup?
   - **Code & Test quality:** Unit tests for each service using `pytest`, integration tests for the workflow, and comparing the complexity of the error-handling code.

→ Learning Outcomes: Software Engineering (LO1), Software Quality (LO2), Software Maintenance (LO3), Professional Standard (LO4), Personal Leadership (LO5).

## Why is this relevant for you?

This idea came directly out of a problem I faced during a hackathon: a multi-step pipeline failed halfway through, and because there was no clean failure handling, the data was left in an inconsistent mess. I had no solid way to reason about partial failure, and I want to turn that pain point into practical, hands-on knowledge.

This semester is all about building good software: solid architectural principles (like microservices with database-per-service), high software quality, testing (unit and integration tests), and reliable code. Understanding fault tolerance in distributed workflows is a core engineering skill that connects directly to my technical growth and infrastructure work.

My coach (Erik) supported this direction, with the clear condition that I keep the scope realistic. I have two personal experiments to complete this semester, with an allocated budget of around 0.5 days per week (~4–5 hours). To make sure I can deliver a working app, thorough tests, and solid research within ~38 total hours, I am keeping the business logic of each service minimal (one database table each) so I can focus on software quality and the reliability experiment itself.

## Analyzing

- *(LO1 – Software Engineering, LO2 – Software Quality)*

I research and analyze how distributed systems handle transactions compared to traditional single-database systems (ACID vs. BASE, 2-Phase Commit vs. the Saga pattern).

I define concrete, measurable quality criteria before running the experiments:

- **Consistency rate:** The percentage of transactions that end up in a clean state (either 100% completed or 100% rolled back) versus an orphaned state.
- **Recovery time:** How quickly the system resumes or rolls back after a crash.
- **Error-handling complexity:** The lines of boilerplate code and mental overhead required to maintain rollback logic in a naive script vs. Temporal.

## Designing

- *(LO3 – Software Maintenance, LO1 – Software Engineering)*

I design the system following clear microservice principles:

- **Database-per-service:** Flight, Hotel, and Payment each own their own independent SQLite database. No service can directly query or modify another service's tables.
- **Service autonomy & API contracts:** Each service exposes clear REST endpoints with standard JSON request and response schemas (via Pydantic), including dedicated compensation endpoints (`/cancel`, `/refund`).
- **Failure injection mechanism:** A clean way to simulate failure (e.g., a test header `x-fail: true` or a chaos route) so crashes can be triggered deterministically during automated integration tests or from the UI.
- **Architecture design:** Documenting both the naive direct-call flow and the Temporal saga state machine using sequence and architecture diagrams.

## Realizing

- *(LO2 – Software Quality, LO1 – Software Engineering)*

I build the system incrementally using version control and proper engineering practices:

- **Microservices & UI:** Implement the three services using Python (FastAPI) and a lightweight UI dashboard in React (Vite) to interact with them and see live booking statuses.
- **Automated Testing:** Write unit tests for each individual service and integration tests covering the complete booking flow using `pytest` and `httpx` async test clients.
- **Version A (Naive):** Implement the simple sequential booking script and log the state transitions.
- **Version B (Temporal):** Set up local Temporal (`temporal server start-dev`), implement the saga workflow with the `temporalio` Python SDK, and register the compensating activities.
- **Experiment Execution:** Run automated crash tests against both versions, capture database snapshots of the state, and use Temporal's built-in web UI to inspect the workflow event history.

## Advising

- *(LO4 – Professional Standard)*

I write an evidence-based technical advice document (structured as an Architectural Decision Record, or ADR) for my portfolio and project team.

Instead of just repeating marketing claims about Temporal, I base my advice on real data from my tests:

- When is a lightweight script with try/catch enough?
- At what point does a system become complex enough to justify the operational overhead of a workflow engine like Temporal?
- Clear trade-offs covering operational complexity, developer learning curve, and data consistency guarantees.

## Managing & Control

- *(LO5 – Personal Leadership)*

I manage my time and scope strictly to ensure this experiment finishes within ~38 hours, leaving room for my second personal experiment this semester.

I work in 5 clear, bite-sized iterations. At the end of each sprint, I review progress, update my FeedPulse and PDP, and gather feedback from my coach (Erik). If any part threatens to blow up the time budget (like complex UI styling or deep infrastructure tuning), I cut back to keep the core experiment on schedule.

## How are you going to do it?

I will execute the project across 5 structured cycles:

| Cycle | Focus & Method | Deliverable |
| :--- | :--- | :--- |
| **Cycle 1: Research & Problem Scoping** | **Library:** Research Saga pattern, 2PC, ACID vs. BASE, and Temporal architecture. Define failure test scenarios. | A short research summary defining the failure matrix, hypotheses, and quality metrics. |
| **Cycle 2: Microservices & Contracts** | **Workshop & Lab:** Build the 3 services in Python (FastAPI) with SQLite DBs, write unit tests with pytest for forward and compensation endpoints. | Working FastAPI microservices with pytest unit tests and independent SQLite DBs. |
| **Cycle 3: Temporal Workflow & Compensation** | **Workshop & Lab:** De-risk core technology early: start local Temporal server, implement the booking saga with compensating rollbacks using temporalio, and write pytest tests. | Fully working Temporal saga in Python that automatically recovers and compensates after failures. |
| **Cycle 4: Naive Baseline & React UI Dashboard** | **Lab:** Build the naive sequential coordinator script and the 1-page React (Vite) UI dashboard with a crash trigger. Run baseline crash tests. | Naive coordinator, React UI dashboard, and baseline crash test report. |
| **Cycle 5: Comparison & Advisory Report** | **Lab & Advice:** Run identical crash tests on Temporal. Compare metrics, capture UI/flow screenshots, and write the final advice report. | Final comparison report (ADR), portfolio documentation, and review with coach. |

### Cycle Details

- **Cycle 1 — Research & Problem Scoping:**
  Study how partial failures break distributed workflows. Define the exact scenario to test (e.g. crash after flight reservation, crash during payment). Define the data consistency checklist to verify after each test run.

- **Cycle 2 — Microservices & Contracts:**
  Create the Flight, Hotel, and Payment services using Python (FastAPI). Give each its own SQLite database file (`flight.db`, `hotel.db`, `payment.db`). Write unit tests with `pytest` to verify forward (`/reserve`, `/charge`) and compensating (`/cancel`, `/refund`) endpoints.

- **Cycle 3 — Temporal Workflow & Compensation:**
  De-risk the core new technology early: start the local Temporal engine (`temporal server start-dev`). Re-implement the booking workflow as a Temporal Saga using the `temporalio` Python SDK, where each step has a compensating activity. Run integration tests in `pytest` to ensure rollbacks trigger correctly.

- **Cycle 4 — Naive Baseline & React UI Dashboard:**
  Implement the naive sequential controller (straightforward HTTP calls with in-memory `try/except`) to serve as the baseline comparison. Build the simple frontend in React (Vite) to run bookings, view service statuses, and trigger simulated service crashes. Run the baseline crash test and record orphaned database holds.

- **Cycle 5 — Comparison & Advisory Report:**
  Run the crash test against the Temporal version. Document the difference in consistency (orphaned holds vs. clean cancellations) and inspect the runs in Temporal Web UI. Write the final ADR / advice report summarizing trade-offs and recommendations.

## What expertise do you need?

- Backend development & API design with Python (FastAPI, Pydantic, SQLite)
- Software testing practices (unit and integration testing with `pytest` and `httpx`)
- Workflow orchestration with the Temporal Python SDK (`temporalio`)
- Frontend development with React and Vite (building a clean, lightweight control dashboard)
- Microservices design principles (database-per-service, service autonomy, REST contracts)
- Distributed transaction patterns (Saga pattern, compensating actions)
- Pragmatic fault injection (simulating process crashes and network timeouts)

---

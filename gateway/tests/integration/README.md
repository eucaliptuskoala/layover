# Isolated live and crash tests

Run both engines against the actual gateway and service applications without changing local
or Compose data. Each test starts processes on ephemeral loopback ports and writes one database
per service in pytest's temporary directory. Tests stop their own processes at teardown and
leave the logs/databases available in that directory for inspection.

## Run

Install the Temporal CLI and sync the independent projects from the repository root:

```sh
uv sync --directory services/flight
uv sync --directory services/hotel
uv sync --directory services/payment
uv sync --directory orchestrators/temporal
uv sync --directory gateway
```

Run all live and crash scenarios:

```sh
uv run --directory gateway pytest --run-integration tests/integration -v -s
```

Run only the deterministic crash comparison:

```sh
uv run --directory gateway pytest --run-integration tests/integration/test_process_crashes.py -v -s
```

Normal `uv run pytest` skips these tests. The full integration command requires the Temporal
CLI; Docker is not required. Each test starts its own dev server and worker with a unique
namespace/task queue. No process on an existing task queue participates in the experiment.

## Crash checkpoint

Both engines run the `fail_payment` scenario. A test-only payment proxy blocks `/charge`
**before forwarding it to Payment**, after the coordinator has received both reservation
acknowledgments. The test waits on an HTTP arrival event rather than guessing with a sleep,
then verifies flight and hotel are `RESERVED`, payment is absent, and the balance is unchanged.

The test kills only the `Popen` process that it started:

- **Naive:** `SIGKILL` the gateway, restart it without resubmitting the booking, then release
  the proxy. The lost compensation stack has no owner; both holds remain `RESERVED`.
- **Temporal:** `SIGKILL` the worker, restart it, and release the proxy. The server stays alive.
  An activity retry receives the real payment `400`, then the workflow cancels hotel followed
  by flight. Both holds become `CANCELLED`.

After release, the proxy confirms Payment's actual rejection. The test checks final state through
the owning service APIs and emits JSON containing the booking ID, killed process/PID, checkpoint,
before/after states, and Temporal history-event count. The naive assertion proves no automatic
recovery after restart; it does not claim the holds can never be cancelled manually.

## Limits

The proxy is a loopback-only test application, not a production route or UI crash feature. It
does not write service databases. The crash tests compare coordinator loss, not service crashes.
Readiness polling is only for startup; it does not choose the crash instant.

Temporal's dev-server history is in memory by default. This experiment keeps that server alive
and demonstrates worker restart recovery, not server restart durability. Retry policies also
differ: naive makes one attempt, while the existing Temporal workflow allows three forward and
five compensation attempts for retryable failures. Permanent confirmation and rollback failures
still need service-state reconciliation in either engine.

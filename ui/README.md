# Layover UI

React + Vite + TypeScript frontend for the Layover booking experiment. The checkout and
processing screens are translated from [`../ui_template/`](../ui_template/); the original HTML
files are unchanged. Axios calls the existing [`../gateway/`](../gateway/) API. Tailwind CSS v4
and scoped component styles preserve the templates' layout, typography, and illustrations.
Fonts are self-hosted using Fontsource; no Google Fonts connection is required.

## Start locally

Use Node **22.22.2+** on the 22.x line, **24.15.0+** on the 24.x line, or **26+**, and npm.
If you use nvm, `nvm use` reads the provided `.nvmrc`.

From the repository root, start the gateway in one terminal:

```sh
uv run --directory gateway python main.py
```

Start the frontend in another terminal:

```sh
cd ui
npm ci
npm run dev
```

Open <http://localhost:5173>. Vite forwards `/api` requests to <http://localhost:8000>, preserving
the `/api` prefix. The gateway does not need to serve frontend files.

### Run actual booking workflows

Start the three microservices and Temporal before expecting successful bookings. From the
repository root:

```sh
docker compose up -d --build
```

In separate terminals:

```sh
temporal server start-dev --namespace layover
```

```sh
uv run --directory orchestrators/temporal python worker.py
```

The default is **Temporal + Happy Path**. Choose Payment decline or Hotel rejection to run the
gateway's fault scenarios. Changing a scenario changes the actual flight, hotel, prices, and
total submitted to the gateway. The negative hotel price is an intentional HTTP 422 fault
fixture and is not silently corrected by the frontend.

The payment service has persistent test account balances: repeated successful bookings can
exhaust `user_1`'s balance. The displayed **$1,000 demo seed** is the initial fixture balance,
not a live balance. Card choices and itinerary dates/times are illustrative and never submitted
as real payment or itinerary data.

## Configuration

Defaults work without an environment file. To override them, copy `.env.example` to `.env.local`
inside `ui/` and restart Vite.

| Variable                  | Default                 | Purpose                                                                                               |
| ------------------------- | ----------------------- | ----------------------------------------------------------------------------------------------------- |
| `GATEWAY_PROXY_TARGET`    | `http://localhost:8000` | Backend target for the dev/preview proxy; not sent to the browser.                                    |
| `VITE_API_BASE_URL`       | `/api`                  | Axios base URL, **including `/api`**. Use `https://your-gateway.example/api` for a separate API host. |
| `VITE_BOOKING_TIMEOUT_MS` | `300000`                | Five-minute browser request timeout. Values below 1,000 or invalid values use the default.            |
| `VITE_TEMPORAL_UI_URL`    | `http://localhost:8233` | Inspection URL before a result is available.                                                          |
| `VITE_TEMPORAL_NAMESPACE` | `layover`               | Namespace used for the pre-result inspection link.                                                    |

When the gateway returns `temporal_ui_url`, that link takes precedence. Only HTTP(S) URLs
without embedded credentials are allowed.

`VITE_` variables are public, embedded in the build, and **must not contain secrets**. Cross-origin
requests do not send credentials. This app is a local academic sandbox, not a production payment
application; the gateway's existing permissive CORS and lack of authentication are unchanged.

## API and execution behavior

| Endpoint             | Usage                                                                              |
| -------------------- | ---------------------------------------------------------------------------------- |
| `GET /api/scenarios` | Load scenario names, descriptions, customer, flight/hotel identifiers, and prices. |
| `GET /api/health`    | Load service health and probe latency on startup and explicit refresh.             |
| `POST /api/bookings` | Submit a single booking and wait for its final `BookingResponse`.                  |

- The processing screen displays `steps_completed` and `compensations_executed` in their returned
  order, including `confirm_flight` and `confirm_hotel` when present.
- `CONFIRMED`, `COMPENSATED`, and `FAILED` are business outcomes, even when HTTP status is 200.
  Unknown statuses are displayed without assuming success.
- `COMPENSATED` does not guarantee every rollback succeeded. The UI flags completed actions
  whose matching compensation was not reported.
- There is **no live activity stream, booking lookup, or cancellation endpoint**. While pending,
  the UI shows an indeterminate wait, not invented progress or per-step timings. Displayed request
  duration is measured in the browser, not the workflow's execution duration.
- Timeouts, disconnections, HTTP 5xx, and malformed booking responses have **unknown outcomes**:
  the Temporal workflow may still be running. The app never automatically retries a booking.
  Known HTTP validation/permission rejections are shown separately.
- Booking IDs are generated before submission so in-flight/unknown runs can be inspected in
  Temporal. Navigation within the app keeps the request alive. Refreshing a pending run restores
  an unknown outcome without resubmitting it.
- The latest run is kept in **sessionStorage** for the current tab; scenario preference is kept in
  **localStorage**. Downloads are JSON experiment reports with the actual request/result, not
  fabricated tickets, receipts, or payment confirmations.
- **In-memory** and **Worker crash** controls are visible but disabled: those gateway features
  are not implemented. No direct calls are made to service databases or individual microservices.

## Checks

```sh
npm test
npm run typecheck
npm run lint
npm run format:check
npm run build
npm audit
```

For test-driven development:

```sh
npm run test:watch
```

The automated tests use controlled gateway responses and do not charge test accounts. They cover
scenario updates, request contracts, health states, outcome mapping, compensation ordering,
duplicate prevention, transport errors, and refresh/navigation safety.

The `minimatch` override uses a patched 11.x release to avoid
[GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249) in transitive lint dependencies.

## Build and preview

```sh
npm run build
npm run preview
```

Preview is available at <http://localhost:4173> and uses the same local `/api` proxy. For a real
deployment, serve `dist/` with SPA fallback to `index.html` for `/checkout` and `/processing/*`,
and either reverse-proxy `/api` to the gateway or set `VITE_API_BASE_URL` before building. Vite's
development/preview proxy is not part of the production bundle.

## Structure

```text
src/
  api/          Axios client, TypeScript contracts, response validation
  components/   Cards, controls, health panel, topology, execution summary
  hooks/        Read-only resources, explicit booking submission, timers
  lib/          Outcome mapping, safe URLs, persistence, formatting, downloads
  pages/        Checkout and processing routes
  styles/       Tailwind theme and template-specific component layers
tests/          Vitest + React Testing Library tests and gateway fixtures
```

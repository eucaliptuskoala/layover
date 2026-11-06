import { Link, useParams } from 'react-router';

import type { HealthReport } from '../api/contracts';
import { BookingOutcome } from '../components/BookingOutcome';
import { ExecutionSummary } from '../components/ExecutionSummary';
import { Icon } from '../components/Icon';
import { ServiceTopology } from '../components/ServiceTopology';
import { useElapsed } from '../hooks/useElapsed';
import { getOutcome, getTemporalUrl, type BookingRun } from '../lib/booking';
import { formatMoney } from '../lib/format';

export function ProcessingPage({
  run,
  health,
  notify,
}: {
  run: BookingRun | null;
  health: HealthReport | null;
  notify: (message: string) => void;
}) {
  const { bookingId } = useParams();
  const activeRun = run?.request.booking_id === bookingId ? run : null;
  const elapsed = useElapsed(activeRun);
  const response = activeRun?.phase === 'result' ? activeRun.response : null;
  const title = response
    ? getOutcome(response).title
    : activeRun?.phase === 'pending'
      ? 'Reserving your layover'
      : activeRun?.phase === 'rejected'
        ? 'Booking request rejected'
        : 'Booking outcome unknown';
  const temporalUrl = getTemporalUrl(bookingId || '', response?.temporal_ui_url);
  const displayedId = response?.booking_id || bookingId;

  if (!activeRun) {
    return (
      <main className="recovery-page">
        <div className="card p-8 max-w-lg">
          <span className="eyebrow mb-3">Layover sandbox</span>
          <h1 className="text-xl font-bold">No saved booking result</h1>
          <p className="mt-3 text-sm text-muted leading-relaxed">
            This tab has no saved result for <span className="font-mono">{bookingId}</span>. Opening
            this URL does not submit or repeat a booking. The gateway has no booking lookup
            endpoint.
          </p>
          {temporalUrl && (
            <a
              className="btn btn-primary mt-5"
              href={temporalUrl}
              target="_blank"
              rel="noopener noreferrer"
            >
              <Icon name="external" />
              Inspect booking in Temporal
            </a>
          )}
          <Link className="btn btn-ghost mt-2" to="/checkout">
            Back to checkout
          </Link>
        </div>
      </main>
    );
  }

  return (
    <div
      className="processing-page"
      data-outcome={activeRun.phase === 'result' ? response?.status.toLowerCase() : activeRun.phase}
    >
      <a className="skip-link" href="#main">
        Skip to booking result
      </a>
      <header className="topbar">
        <div className="processing-topbar-inner">
          <Link className="back-link" to="/checkout" aria-label="Back to checkout">
            <Icon name="left" />
            <span>Back to checkout</span>
          </Link>
          <div className="transaction-id">
            <span className="status-dot" />
            <span>{displayedId}</span>
          </div>
          <div className="engine-badge">
            <span className="status-dot" />
            <span>
              <b>Temporal</b>
              <small>durable saga</small>
            </span>
          </div>
        </div>
      </header>

      <main id="main" className="processing-main">
        <header className="processing-page-header">
          <div>
            <span className="eyebrow text-emerald-800">
              <span className="status-dot" />
              Saga experiment{' '}
              <span className="text-faint">
                / {activeRun.phase === 'pending' ? 'in flight' : 'gateway summary'}
              </span>
            </span>
            <h1>{title}</h1>
            <p>
              {activeRun.scenario.flight_number} <span className="metadata-separator">·</span>{' '}
              {activeRun.scenario.hotel_name}
              <span className="metadata-separator">·</span>
              <span className="font-mono text-ink">
                {formatMoney(response?.total_amount ?? activeRun.scenario.expected_total)}
              </span>{' '}
              requested
            </p>
          </div>
          <div className="processing-total">
            <span>Scenario total</span>
            <strong>{formatMoney(activeRun.scenario.expected_total)}</strong>
            <small>USD · test transaction</small>
          </div>
        </header>

        <ServiceTopology
          response={response}
          isPending={activeRun.phase === 'pending'}
          elapsed={elapsed}
          health={health}
        />
        <div className="processing-grid">
          <ExecutionSummary run={activeRun} elapsed={elapsed} notify={notify} />
          <BookingOutcome run={activeRun} elapsed={elapsed} notify={notify} />
          <section className="developer-actions card" aria-label="Developer actions">
            <h2 className="eyebrow">Developer</h2>
            {temporalUrl ? (
              <a
                className="developer-action"
                href={temporalUrl}
                target="_blank"
                rel="noopener noreferrer"
              >
                <span className="action-icon">
                  <Icon name="external" />
                </span>
                <span>
                  <strong>Open in Temporal Web UI</strong>
                  <small>
                    {response?.temporal_ui_url
                      ? 'Workflow link returned by the gateway'
                      : 'Inspect workflow · configured namespace'}
                  </small>
                </span>
                <Icon name="right" />
              </a>
            ) : (
              <p className="text-xs text-muted py-3">
                No safe Temporal workflow link is available.
              </p>
            )}
            <Link className="developer-action" to="/checkout">
              <span className="action-icon">
                <Icon name="refresh" />
              </span>
              <span>
                <strong>
                  {activeRun.phase === 'pending' ? 'Return to checkout' : 'Run another test'}
                </strong>
                <small>Scenario preserved · new bookings require confirmation</small>
              </span>
              <Icon name="right" />
            </Link>
          </section>
        </div>
      </main>
    </div>
  );
}

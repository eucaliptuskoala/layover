import { useState } from 'react';
import { Link } from 'react-router';

import type { HealthReport, Scenario, ScenarioKey } from '../api/contracts';
import { Icon } from '../components/Icon';
import { PriceSummary } from '../components/PriceSummary';
import { SandboxPanel } from '../components/SandboxPanel';
import { TripDetails, TripHeader } from '../components/TripDetails';
import type { Resource } from '../hooks/useResource';
import type { BookingRun } from '../lib/booking';

export function CheckoutPage({
  scenarios,
  selectedKey,
  onSelect,
  health,
  run,
  onSubmit,
  notify,
}: {
  scenarios: Resource<Scenario[]>;
  selectedKey: ScenarioKey;
  onSelect: (key: ScenarioKey) => void;
  health: Resource<HealthReport>;
  run: BookingRun | null;
  onSubmit: (scenario: Scenario) => void;
  notify: (message: string) => void;
}) {
  const [isSandboxOpen, setSandboxOpen] = useState(
    () => !window.matchMedia('(max-width: 620px)').matches,
  );
  const [acknowledgedRun, setAcknowledgedRun] = useState<string | null>(null);
  const selected =
    scenarios.data?.find((scenario) => scenario.key === selectedKey) || scenarios.data?.[0];
  const isPending = run?.phase === 'pending';
  const needsAcknowledgment =
    run?.phase === 'unknown' && acknowledgedRun !== run.request.booking_id;

  return (
    <div className="checkout-page" data-sandbox-open={isSandboxOpen}>
      <a className="skip-link" href="#main">
        Skip to checkout
      </a>
      <header className="topbar">
        <div className="checkout-topbar-inner">
          <Link className="brand" to="/checkout" aria-label="Layover checkout">
            <Icon name="plane" />
            <span>LAYOVER</span>
          </Link>
          <div
            className="account-badge"
            aria-label="Demo account, initial seed balance 1000 dollars, not a live balance"
          >
            <span className="account-avatar" aria-hidden="true">
              u1
            </span>
            <span className="font-mono text-xs">{selected?.customer_id || 'user_1'}</span>
            <span className="account-separator" />
            <span className="account-seed">Demo seed</span>
            <span className="font-mono text-xs font-semibold">$1,000.00</span>
          </div>
        </div>
      </header>

      <main id="main" className="checkout-main">
        <div className="checkout-column">
          <TripHeader />
          {run && (
            <div className={`booking-banner ${needsAcknowledgment ? 'warning' : ''}`}>
              <p>
                {isPending
                  ? 'A booking is already in progress.'
                  : run.phase === 'unknown'
                    ? 'The previous booking has an unknown outcome. Inspect it before running another test.'
                    : 'Your last booking result is saved in this tab.'}
              </p>
              <Link to={`/processing/${encodeURIComponent(run.request.booking_id)}`}>
                {isPending ? 'View active booking' : 'View last booking'} →
              </Link>
              {run.phase === 'unknown' && (
                <label className="flex items-start gap-2 mt-2 text-xs">
                  <input
                    type="checkbox"
                    checked={!needsAcknowledgment}
                    onChange={(event) => {
                      setAcknowledgedRun(event.target.checked ? run.request.booking_id : null);
                    }}
                  />
                  I checked the previous workflow and understand that another test creates a new
                  booking.
                </label>
              )}
            </div>
          )}

          {scenarios.status === 'loading' && !scenarios.data ? (
            <div className="card loading-card" role="status">
              <span className="button-spinner" />
              Loading gateway scenarios…
            </div>
          ) : scenarios.status === 'error' ? (
            <div className="card loading-card" role="alert">
              <Icon name="alert" />
              <h2 className="text-base font-bold">Could not load booking scenarios</h2>
              <p className="text-muted text-sm">{scenarios.error}</p>
              <button className="btn btn-primary" onClick={scenarios.refresh}>
                Retry scenarios
              </button>
            </div>
          ) : selected ? (
            <div className="checkout-stack">
              <TripDetails scenario={selected} />
              <PriceSummary
                scenario={selected}
                isPending={isPending}
                isDisabled={Boolean(needsAcknowledgment)}
                onSubmit={() => onSubmit(selected)}
                notify={notify}
              />
            </div>
          ) : (
            <div className="card loading-card" role="alert">
              <h2 className="text-base font-bold">No scenarios available</h2>
              <p className="text-sm text-muted">The gateway returned an empty scenario catalog.</p>
              <button className="btn btn-primary" onClick={scenarios.refresh}>
                Retry scenarios
              </button>
            </div>
          )}
          <p className="checkout-legal">
            Academic sandbox · itinerary and card details are illustrative. Service health, booking
            outcomes and reported actions are real gateway data.
          </p>
        </div>
      </main>

      <SandboxPanel
        scenarios={scenarios.data || []}
        selectedKey={(selected?.key as ScenarioKey) || selectedKey}
        onSelect={onSelect}
        health={health}
        isOpen={isSandboxOpen}
        onToggle={() => setSandboxOpen((previous) => !previous)}
        isDisabled={isPending}
      />
    </div>
  );
}

import type { Scenario } from '../api/contracts';
import { formatMoney } from '../lib/format';
import { CanalIllustration } from './CanalIllustration';
import { Icon } from './Icon';

function getCarrier(flight: string) {
  if (flight.startsWith('LH')) return { name: 'Lufthansa', mark: 'LH' };
  if (flight.startsWith('KLM')) return { name: 'KLM', mark: 'KL' };
  if (flight.startsWith('AF')) return { name: 'Air France', mark: 'AF' };
  return { name: 'Test flight', mark: flight.slice(0, 2) };
}

export function TripHeader() {
  return (
    <header className="trip-header">
      <div className="flex items-center justify-between gap-3">
        <span className="eyebrow">
          <span className="status-dot" />
          Boutique checkout
        </span>
        <span className="eyebrow">
          <Icon name="lock" />
          Test environment
        </span>
      </div>
      <h1 className="route" aria-label="Frankfurt to Amsterdam — illustrative itinerary">
        <span className="route-end">
          Frankfurt <small>(FRA)</small>
        </span>
        <span className="route-arch" aria-hidden="true">
          <svg viewBox="0 0 260 30" preserveAspectRatio="none">
            <path
              d="M2 25C64 4 196 4 258 25"
              fill="none"
              stroke="#E7C79A"
              strokeWidth="1.2"
              strokeDasharray="3 5"
              strokeLinecap="round"
            />
            <circle cx="2" cy="25" r="2" fill="#D97706" opacity=".5" />
            <circle cx="258" cy="25" r="2" fill="#D97706" opacity=".5" />
          </svg>
          <span className="route-plane">
            <Icon name="plane" />
          </span>
          <span className="route-duration">1H 15M · DIRECT</span>
        </span>
        <span className="route-end text-right">
          Amsterdam <small>(AMS)</small>
        </span>
      </h1>
      <div className="trip-meta">
        <span>
          <Icon name="calendar" />
          Sat, 14 Nov 2026
        </span>
        <span>
          <Icon name="clock" />
          09:40 → 10:55
        </span>
        <span>1 traveler · Economy</span>
      </div>
      <p className="itinerary-note">
        Illustrative itinerary · booking values come from the selected gateway scenario
      </p>
    </header>
  );
}

export function TripDetails({ scenario }: { scenario: Scenario }) {
  const carrier = getCarrier(scenario.flight_number);
  return (
    <>
      <article className="boarding-pass" aria-label={`Flight ${scenario.flight_number}`}>
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="carrier-mark" aria-hidden="true">
              {carrier.mark}
            </span>
            <span className="text-[13px] font-semibold">{carrier.name}</span>
            <span className="flight-number">{scenario.flight_number}</span>
          </div>
          <div className="flight-times">
            <div>
              <strong>09:40</strong>
              <small>FRA</small>
            </div>
            <div className="flight-line" aria-hidden="true">
              <Icon name="plane" />
            </div>
            <div className="text-right">
              <strong>10:55</strong>
              <small>AMS</small>
            </div>
          </div>
        </div>
        <div className="flight-price">
          <span>Fare</span>
          <strong>{formatMoney(scenario.flight_price)}</strong>
        </div>
      </article>

      <article className="hotel-card" aria-label={`Hotel ${scenario.hotel_name}`}>
        <div className="hotel-thumbnail">
          <CanalIllustration />
        </div>
        <div className="min-w-0">
          <div className="flex items-baseline justify-between gap-3">
            <span className="hotel-name">{scenario.hotel_name}</span>
            <span className="font-mono text-xs font-semibold whitespace-nowrap">
              {formatMoney(scenario.hotel_price)}
            </span>
          </div>
          <p className="mt-1 text-[11.5px] text-muted">
            {scenario.hotel_price < 0
              ? 'Fault fixture · intentionally invalid price'
              : '2 nights · Nov 14–16 · illustrative dates'}
          </p>
        </div>
      </article>
    </>
  );
}

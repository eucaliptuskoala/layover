import { useRef, useState } from 'react';

import type { Scenario } from '../api/contracts';
import { formatMoney } from '../lib/format';
import { Icon } from './Icon';

export function PriceSummary({
  scenario,
  isPending,
  isDisabled,
  onSubmit,
  notify,
}: {
  scenario: Scenario;
  isPending: boolean;
  isDisabled: boolean;
  onSubmit: () => void;
  notify: (message: string) => void;
}) {
  const [isCardMenuOpen, setCardMenuOpen] = useState(false);
  const [card, setCard] = useState<'Visa' | 'Amex'>('Visa');
  const changeButton = useRef<HTMLButtonElement>(null);

  function closeCardMenu() {
    setCardMenuOpen(false);
    changeButton.current?.focus({ preventScroll: true });
  }

  return (
    <section className="card price-summary" aria-label="Price summary and payment">
      <div className="flex items-center justify-between gap-3">
        <h2 className="eyebrow">Price breakdown</h2>
        <span className="font-mono text-[10px] text-faint tracking-wider">CURRENCY · USD</span>
      </div>
      <div className="price-rows">
        <div>
          <span>
            Flight · {scenario.flight_number}
            <em>1 PAX</em>
          </span>
          <span>{formatMoney(scenario.flight_price)}</span>
        </div>
        <div>
          <span>
            Hotel<em>SCENARIO PRICE</em>
          </span>
          <span>{formatMoney(scenario.hotel_price)}</span>
        </div>
        <div>
          <span>Additional fees</span>
          <span className="included">NONE IN SANDBOX</span>
        </div>
      </div>
      <div className="price-total">
        <span>
          Total <small>USD</small>
        </span>
        <strong>{formatMoney(scenario.expected_total)}</strong>
      </div>

      <div className="saga-note">
        <span className="saga-icon">
          <Icon name="shield" />
        </span>
        <span className="flex-1 min-w-0">
          <strong>Coordinated by the Layover Saga</strong>
          <span>Compensating actions are attempted when a booking step fails.</span>
        </span>
        <span className="font-mono text-[10px] text-faint whitespace-nowrap saga-meta">
          3 svc · 1 workflow
        </span>
      </div>

      <div
        className="payment-method"
        onKeyDown={(event) => {
          if (event.key === 'Escape' && isCardMenuOpen) {
            event.preventDefault();
            closeCardMenu();
          }
        }}
      >
        <div className="flex items-center gap-2.5">
          <span className="demo-card" data-brand={card} aria-hidden="true" />
          <span className="flex-1 min-w-0">
            <span className="block text-[10px] text-faint">Demo payment method · display only</span>
            <span className="block text-xs font-medium">
              <span className="font-mono">
                {card} ···· {card === 'Visa' ? '4412' : '1009'}
              </span>
            </span>
          </span>
          <button
            ref={changeButton}
            className="change-card"
            type="button"
            aria-expanded={isCardMenuOpen}
            aria-controls="demo-cards"
            onClick={() => setCardMenuOpen((previous) => !previous)}
          >
            Change
            <Icon name="down" />
          </button>
        </div>
        {isCardMenuOpen && (
          <fieldset id="demo-cards" className="demo-card-options">
            <legend className="sr-only">Demo payment methods</legend>
            {(['Visa', 'Amex'] as const).map((brand) => (
              <label key={brand} className="flex items-center gap-2">
                <input
                  type="radio"
                  name="demo-card"
                  checked={card === brand}
                  onChange={() => {
                    setCard(brand);
                    closeCardMenu();
                    notify(`${brand} selected for display. Bookings use the test account balance.`);
                  }}
                />
                <span>
                  {brand} ···· {brand === 'Visa' ? '4412' : '1009'}
                </span>
              </label>
            ))}
          </fieldset>
        )}
      </div>

      <button
        className="pay-button"
        type="button"
        onClick={onSubmit}
        disabled={isDisabled || isPending}
        aria-label={
          isPending
            ? 'Booking in progress'
            : `Confirm & Pay (${formatMoney(scenario.expected_total)})`
        }
      >
        {isPending && <span className="button-spinner" aria-hidden="true" />}
        <span>{isPending ? 'Booking in progress' : 'Confirm & Pay'}</span>
        {!isPending && (
          <>
            <span className="pay-amount">({formatMoney(scenario.expected_total)})</span>
            <span aria-hidden="true">→</span>
          </>
        )}
      </button>
      <p className="payment-caption">
        <Icon name="lock" />
        Test account only · no real card is charged
      </p>
    </section>
  );
}

import { useRef, useState } from 'react';

import { isScenarioKey, type Scenario } from '../api/contracts';
import { createBooking, getBookingError } from '../api/gateway';
import type { BookingRun } from '../lib/booking';
import { readRun, saveRun } from '../lib/storage';

function createBookingId() {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return `bk-${Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')}`;
}

export function useBooking() {
  const [run, setRun] = useState<BookingRun | null>(readRun);
  const isSubmitting = useRef(false);

  function publish(next: BookingRun) {
    saveRun(next);
    setRun(next);
  }

  function startBooking(scenario: Scenario): string | null {
    if (isSubmitting.current || !isScenarioKey(scenario.key)) return null;

    const bookingId = createBookingId();
    const next: BookingRun = {
      phase: 'pending',
      startedAt: Date.now(),
      scenario: { ...scenario },
      request: {
        booking_id: bookingId,
        orchestrator: 'temporal',
        scenario: scenario.key,
        customer_id: scenario.customer_id,
        flight_number: scenario.flight_number,
        flight_price: scenario.flight_price,
        hotel_name: scenario.hotel_name,
        hotel_price: scenario.hotel_price,
      },
    };
    const started = performance.now();
    isSubmitting.current = true;
    publish(next);

    // Submit from an explicit user event, never a mount effect. Navigation does not cancel it.
    void createBooking(next.request)
      .then((response) => {
        publish({
          ...next,
          phase: 'result',
          response,
          durationMs: Math.round(performance.now() - started),
        });
      })
      .catch((error: unknown) => {
        const { kind, message } = getBookingError(error);
        publish({
          ...next,
          phase: kind,
          message,
          durationMs: Math.round(performance.now() - started),
        });
      })
      .finally(() => {
        isSubmitting.current = false;
      });

    return bookingId;
  }

  return { run, startBooking };
}

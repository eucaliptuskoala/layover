import type { BookingRequest, BookingResponse, Scenario } from '../api/contracts';

export type BookingRun = {
  request: BookingRequest & { booking_id: string };
  scenario: Scenario;
  startedAt: number;
} & (
  | { phase: 'pending' }
  | { phase: 'result'; response: BookingResponse; durationMs: number }
  | { phase: 'unknown' | 'rejected'; message: string; durationMs?: number }
);

export type Tone = 'mint' | 'coral' | 'amber' | 'neutral';
export type ServiceState =
  'confirmed' | 'reserved' | 'charged' | 'cancelled' | 'refunded' | 'unreported';

const STEP_LABELS: Record<string, string> = {
  reserve_flight: 'Reserve flight',
  reserve_hotel: 'Reserve hotel',
  charge_payment: 'Charge payment',
  confirm_flight: 'Confirm flight',
  confirm_hotel: 'Confirm hotel',
  cancel_flight: 'Cancel flight',
  cancel_hotel: 'Cancel hotel',
  refund_payment: 'Refund payment',
};

export function getStepLabel(step: string): string {
  return STEP_LABELS[step] || step;
}

export function getServiceStates(response: BookingResponse | null) {
  const steps = response?.steps_completed || [];
  const compensations = response?.compensations_executed || [];
  return {
    flight: compensations.includes('cancel_flight')
      ? 'cancelled'
      : steps.includes('confirm_flight')
        ? 'confirmed'
        : steps.includes('reserve_flight')
          ? 'reserved'
          : 'unreported',
    hotel: compensations.includes('cancel_hotel')
      ? 'cancelled'
      : steps.includes('confirm_hotel')
        ? 'confirmed'
        : steps.includes('reserve_hotel')
          ? 'reserved'
          : 'unreported',
    payment: compensations.includes('refund_payment')
      ? 'refunded'
      : steps.includes('charge_payment')
        ? 'charged'
        : 'unreported',
  } as Record<'flight' | 'hotel' | 'payment', ServiceState>;
}

export function getOutcome(response: BookingResponse): {
  label: string;
  title: string;
  tone: Tone;
  icon: string;
  note: string;
} {
  if (response.status === 'CONFIRMED') {
    return {
      label: 'CONFIRMED',
      title: 'Layover confirmed',
      tone: 'mint',
      icon: '✓',
      note: 'The gateway reports that the booking workflow completed successfully.',
    };
  }
  if (response.status === 'COMPENSATED') {
    const states = getServiceStates(response);
    const outstanding = Object.values(states).some((state) =>
      ['reserved', 'confirmed', 'charged'].includes(state),
    );
    return {
      label: 'COMPENSATED',
      title: 'Booking rolled back',
      tone: 'coral',
      icon: '↺',
      note: outstanding
        ? 'The gateway reports COMPENSATED, but not all completed actions have a reported rollback. Inspect the workflow.'
        : 'The booking did not complete. Reported compensations are listed below in execution order.',
    };
  }
  if (response.status === 'FAILED') {
    return {
      label: 'FAILED',
      title: 'Booking failed',
      tone: 'coral',
      icon: '!',
      note: 'The gateway reports a failed booking. Review the error and reported actions below.',
    };
  }
  return {
    label: response.status || 'UNKNOWN',
    title: 'Unrecognized booking outcome',
    tone: 'amber',
    icon: '?',
    note: 'The gateway returned an unrecognized status. No successful booking or rollback is assumed.',
  };
}

function safeHttpUrl(value: string): string | null {
  try {
    const url = new URL(value);
    return ['http:', 'https:'].includes(url.protocol) && !url.username && !url.password
      ? url.href
      : null;
  } catch {
    return null;
  }
}

export function getTemporalUrl(bookingId: string, suppliedUrl?: string | null): string | null {
  if (suppliedUrl != null) return safeHttpUrl(suppliedUrl);
  const base = safeHttpUrl(import.meta.env.VITE_TEMPORAL_UI_URL || 'http://localhost:8233');
  if (!base) return null;
  const namespace = import.meta.env.VITE_TEMPORAL_NAMESPACE || 'layover';
  return `${base.replace(/\/$/, '')}/namespaces/${encodeURIComponent(namespace)}/workflows/${encodeURIComponent(bookingId)}`;
}

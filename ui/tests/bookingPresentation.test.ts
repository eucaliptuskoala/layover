import { describe, expect, it } from 'vitest';

import { getOutcome, getServiceStates, getStepLabel, getTemporalUrl } from '../src/lib/booking';
import { confirmedResponse } from './fixtures';

describe('booking presentation', () => {
  it('includes reservation confirmation steps and keeps unknown step names', () => {
    expect(getStepLabel('confirm_flight')).toBe('Confirm flight');
    expect(getStepLabel('confirm_hotel')).toBe('Confirm hotel');
    expect(getStepLabel('future_step')).toBe('future_step');
  });

  it('marks only completed compensations as cancelled or refunded', () => {
    const result = {
      ...confirmedResponse,
      status: 'COMPENSATED',
      steps_completed: ['reserve_flight', 'reserve_hotel'],
      compensations_executed: ['cancel_hotel'],
      error_message: 'Insufficient funds',
    };

    expect(getServiceStates(result)).toMatchObject({
      flight: 'reserved',
      hotel: 'cancelled',
      payment: 'unreported',
    });
    expect(getOutcome(result).note).toContain('not all');
  });

  it('does not treat an unexpected status as a successful booking', () => {
    expect(getOutcome({ ...confirmedResponse, status: 'UNKNOWN' })).toMatchObject({
      label: 'UNKNOWN',
      tone: 'amber',
    });
  });

  it('uses a gateway-supplied workflow URL and rejects unsafe protocols', () => {
    expect(getTemporalUrl('bk-test', confirmedResponse.temporal_ui_url, 'temporal')).toBe(
      confirmedResponse.temporal_ui_url,
    );
    expect(getTemporalUrl('bk-test', 'javascript:alert(1)', 'temporal')).toBeNull();
    expect(getTemporalUrl('bk-test', 'https://user:password@example.com', 'temporal')).toBeNull();
  });

  it('builds an inspection URL using the configured namespace with encoded path values', () => {
    expect(getTemporalUrl('bk test', null, 'temporal')).toBe(
      'http://localhost:8233/namespaces/layover/workflows/bk%20test',
    );
  });

  it('never builds a Temporal link for naive or missing engine context', () => {
    expect(getTemporalUrl('bk-naive', confirmedResponse.temporal_ui_url, 'naive')).toBeNull();
    expect(getTemporalUrl('bk-naive', null, 'naive')).toBeNull();
    expect(getTemporalUrl('bk-missing')).toBeNull();
  });
});

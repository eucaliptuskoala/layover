import { AxiosError } from 'axios';
import { describe, expect, it, vi } from 'vitest';

import {
  apiClient,
  createBooking,
  getBookingError,
  getHealth,
  getScenarios,
} from '../src/api/gateway';
import { confirmedResponse, healthyReport, scenarios } from './fixtures';

describe('gateway client', () => {
  it('loads and validates scenario metadata without rejecting deliberate negative fault prices', async () => {
    const get = vi.spyOn(apiClient, 'get').mockResolvedValue({ data: scenarios });
    const controller = new AbortController();

    expect(await getScenarios(controller.signal)).toEqual(scenarios);
    expect(get).toHaveBeenCalledWith('/scenarios', { signal: controller.signal });
  });

  it('loads real health telemetry', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue({ data: healthyReport });

    expect(await getHealth()).toEqual(healthyReport);
  });

  it('rejects malformed API responses instead of showing fabricated data', async () => {
    vi.spyOn(apiClient, 'get').mockResolvedValue({ data: { services: 'not an array' } });

    await expect(getHealth()).rejects.toThrow('unexpected response');
  });

  it('posts once with a workflow-friendly timeout and treats HTTP 200 FAILED as a result', async () => {
    const result = { ...confirmedResponse, status: 'FAILED', error_message: 'Worker unavailable' };
    const post = vi.spyOn(apiClient, 'post').mockResolvedValue({ data: result });
    const request = {
      booking_id: 'bk-test',
      orchestrator: 'temporal' as const,
      scenario: 'happy_path' as const,
    };

    expect(await createBooking(request)).toEqual(result);
    expect(post).toHaveBeenCalledExactlyOnceWith('/bookings', request, { timeout: 300_000 });
  });

  it('retains unexpected outcome and step identifiers for honest display', async () => {
    const result = { ...confirmedResponse, status: 'SOMETHING_NEW', steps_completed: ['new_step'] };
    vi.spyOn(apiClient, 'post').mockResolvedValue({ data: result });

    expect(await createBooking({ orchestrator: 'temporal', scenario: 'happy_path' })).toEqual(
      result,
    );
  });

  it('does not confuse a timeout or HTTP 500 with a confirmed workflow failure', () => {
    expect(getBookingError(new AxiosError('timeout', 'ECONNABORTED')).kind).toBe('unknown');
    const serverError = new AxiosError('server error', 'ERR_BAD_RESPONSE');
    serverError.response = {
      status: 500,
      data: {},
      statusText: '',
      headers: {},
      config: { headers: {} },
    } as AxiosError['response'];

    expect(getBookingError(serverError).kind).toBe('unknown');
  });

  it('reports HTTP 422 validation as rejected rather than a running workflow', () => {
    const error = new AxiosError('validation failed', 'ERR_BAD_REQUEST');
    error.response = {
      status: 422,
      data: { detail: [{ loc: ['body', 'orchestrator'], msg: 'Invalid orchestrator' }] },
      statusText: '',
      headers: {},
      config: { headers: {} },
    } as AxiosError['response'];

    expect(getBookingError(error)).toEqual({
      kind: 'rejected',
      message: 'Request rejected (HTTP 422). Invalid orchestrator',
    });
  });
});

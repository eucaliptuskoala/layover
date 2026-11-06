import axios from 'axios';

import {
  isBookingResponse,
  isHealthReport,
  isRecord,
  isScenario,
  type BookingRequest,
  type BookingResponse,
  type HealthReport,
  type Scenario,
} from './contracts';

export const apiClient = axios.create({
  baseURL: (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, ''),
  timeout: 15_000,
  withCredentials: false,
  headers: { Accept: 'application/json' },
});

function unexpectedResponse(): never {
  throw new Error('Gateway returned an unexpected response. Check the gateway API version.');
}

export async function getScenarios(signal?: AbortSignal): Promise<Scenario[]> {
  const { data } = await apiClient.get<unknown>('/scenarios', { signal });
  if (!Array.isArray(data) || !data.every(isScenario)) unexpectedResponse();
  return data;
}

export async function getHealth(signal?: AbortSignal): Promise<HealthReport> {
  const { data } = await apiClient.get<unknown>('/health', { signal });
  if (!isHealthReport(data)) unexpectedResponse();
  return data;
}

export async function createBooking(request: BookingRequest): Promise<BookingResponse> {
  const configuredTimeout = Number(import.meta.env.VITE_BOOKING_TIMEOUT_MS);
  const timeout =
    Number.isFinite(configuredTimeout) && configuredTimeout >= 1000 ? configuredTimeout : 300_000;
  const { data } = await apiClient.post<unknown>('/bookings', request, { timeout });
  if (!isBookingResponse(data)) unexpectedResponse();
  return data;
}

export function getErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    if (!error.response) {
      return 'Cannot reach the gateway. Check that it is running and try refreshing.';
    }
    return `Gateway request failed (HTTP ${error.response.status}).`;
  }
  return error instanceof Error ? error.message : 'An unexpected error occurred.';
}

export function getBookingError(error: unknown): { kind: 'unknown' | 'rejected'; message: string } {
  if (axios.isAxiosError(error) && error.response) {
    const { status, data } = error.response;
    // Only validation/permission rejections are known not to have executed the workflow.
    if ([400, 401, 403, 404, 405, 422].includes(status)) {
      const detail = isRecord(data) ? data.detail : undefined;
      const message =
        typeof detail === 'string'
          ? detail
          : Array.isArray(detail)
            ? detail
                .filter(isRecord)
                .map((item) => (typeof item.msg === 'string' ? item.msg : 'Invalid request'))
                .join('; ')
            : 'Check the selected scenario and gateway configuration.';
      return { kind: 'rejected', message: `Request rejected (HTTP ${status}). ${message}` };
    }
  }

  return {
    kind: 'unknown',
    message:
      'The gateway did not return a usable result. The workflow may still be running. ' +
      'Inspect this booking in Temporal before starting another test; it has not been retried.',
  };
}

import {
  isBookingResponse,
  isRecord,
  isScenario,
  isScenarioKey,
  type ScenarioKey,
} from '../api/contracts';
import type { BookingRun } from './booking';

const SCENARIO_KEY = 'layover.ui.scenario.v1';
const RUN_KEY = 'layover.ui.run.v1';

export function readScenario(): ScenarioKey {
  try {
    const value = localStorage.getItem(SCENARIO_KEY);
    return isScenarioKey(value) && value !== 'custom' ? value : 'happy_path';
  } catch {
    return 'happy_path';
  }
}

export function saveScenario(value: ScenarioKey) {
  try {
    localStorage.setItem(SCENARIO_KEY, value);
  } catch {
    // Preferences are optional; private browsing/storage policies must not block booking.
  }
}

export function saveRun(run: BookingRun) {
  try {
    sessionStorage.setItem(RUN_KEY, JSON.stringify(run));
  } catch {
    // The in-memory run remains usable even when session storage is unavailable.
  }
}

export function readRun(): BookingRun | null {
  try {
    const raw = sessionStorage.getItem(RUN_KEY);
    if (!raw || raw.length > 250_000) return null;
    const value: unknown = JSON.parse(raw);
    if (
      !isRecord(value) ||
      !isRecord(value.request) ||
      typeof value.request.booking_id !== 'string' ||
      !value.request.booking_id ||
      !['temporal', 'naive'].includes(String(value.request.orchestrator)) ||
      !isScenarioKey(value.request.scenario) ||
      !isScenario(value.scenario) ||
      typeof value.startedAt !== 'number' ||
      !Number.isFinite(value.startedAt)
    ) {
      return null;
    }

    if (value.phase === 'pending') {
      return {
        ...value,
        phase: 'unknown',
        message:
          'This page was refreshed before a result was saved. The workflow may still be running. ' +
          'Inspect this booking in Temporal; it has not been resubmitted.',
      } as BookingRun;
    }
    if (
      value.phase === 'result' &&
      isBookingResponse(value.response) &&
      typeof value.durationMs === 'number' &&
      Number.isFinite(value.durationMs) &&
      value.durationMs >= 0
    ) {
      return value as BookingRun;
    }
    if (
      ['unknown', 'rejected'].includes(String(value.phase)) &&
      typeof value.message === 'string'
    ) {
      return value as BookingRun;
    }
    return null;
  } catch {
    return null;
  }
}

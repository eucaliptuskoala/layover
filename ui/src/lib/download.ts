import type { BookingRun } from './booking';

export function downloadRun(run: BookingRun) {
  const content = {
    report: 'Layover booking experiment',
    submitted_at: new Date(run.startedAt).toISOString(),
    browser_request_duration_ms: run.phase === 'pending' ? null : (run.durationMs ?? null),
    phase: run.phase,
    request: run.request,
    scenario: run.scenario,
    result: run.phase === 'result' ? run.response : null,
    note: run.phase === 'unknown' || run.phase === 'rejected' ? run.message : null,
    telemetry_note:
      'Final gateway summary only. Per-step timestamps and durations are not available.',
  };
  const blob = new Blob([JSON.stringify(content, null, 2)], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `layover-${run.request.booking_id.replace(/[^a-zA-Z0-9_-]/g, '_')}.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

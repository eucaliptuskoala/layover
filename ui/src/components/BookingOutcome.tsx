import { getOutcome, getServiceStates, type BookingRun } from '../lib/booking';
import { downloadRun } from '../lib/download';
import { formatDuration, formatMoney } from '../lib/format';
import { Icon } from './Icon';

export function BookingOutcome({
  run,
  elapsed,
  notify,
}: {
  run: BookingRun;
  elapsed: number | null;
  notify: (message: string) => void;
}) {
  const response = run.phase === 'result' ? run.response : null;
  const isNaive = run.request.orchestrator === 'naive';
  const presentation = response
    ? getOutcome(response)
    : {
        tone: run.phase === 'rejected' ? 'coral' : 'amber',
        icon: run.phase === 'pending' ? '◌' : '?',
        label:
          run.phase === 'pending'
            ? 'RUNNING'
            : run.phase === 'rejected'
              ? 'REJECTED'
              : 'OUTCOME UNKNOWN',
        note:
          run.phase === 'pending'
            ? isNaive
              ? 'Waiting for the gateway to finish single-attempt HTTP actions. Rollback state exists only in gateway memory.'
              : 'Waiting for the gateway to finish the booking workflow. This can take longer during retries or if a worker is offline.'
            : run.phase === 'unknown' || run.phase === 'rejected'
              ? run.message
              : '',
      };
  const states = getServiceStates(response);

  function download() {
    try {
      downloadRun(run);
      notify('Experiment summary downloaded');
    } catch {
      notify('Could not download the experiment summary.');
    }
  }

  return (
    <aside
      className="outcome-card card"
      data-tone={presentation.tone}
      aria-label="Booking outcome"
      aria-live="polite"
    >
      <div className="outcome-header">
        <div className="flex items-center justify-between gap-3">
          <span className="eyebrow">Outcome</span>
          <span className="font-mono text-[10px] text-faint">{formatDuration(elapsed)}</span>
        </div>
        <div className="outcome-status">
          <span
            className={`outcome-icon ${run.phase === 'pending' ? 'pulse' : ''}`}
            aria-hidden="true"
          >
            {presentation.icon}
          </span>
          <strong>{presentation.label}</strong>
        </div>
        <p className="outcome-note">{presentation.note}</p>
      </div>
      <div className="outcome-body">
        {run.phase === 'pending' ? (
          <>
            <div className="flex items-center justify-between gap-2 text-[11px] text-muted">
              <span>Execution</span>
              <b className="font-mono text-ink">
                {isNaive ? 'In-memory Saga' : 'Temporal workflow'}
              </b>
            </div>
            <div
              className="indeterminate-progress"
              aria-label="Booking in progress"
              role="progressbar"
            />
            <p className="text-[11px] text-muted mt-3">
              This request is submitted once. Navigating within this app does not cancel the
              booking.
            </p>
          </>
        ) : (
          <>
            <dl className="outcome-values">
              <div>
                <dt>Booking ID</dt>
                <dd className="font-mono text-[10px]">
                  {response?.booking_id || run.request.booking_id}
                </dd>
              </div>
              <div>
                <dt>Scenario</dt>
                <dd className="font-mono text-[11px]">
                  {response?.scenario || run.request.scenario}
                </dd>
              </div>
              <div>
                <dt>Requested total</dt>
                <dd>{formatMoney(response?.total_amount ?? run.scenario.expected_total)}</dd>
              </div>
              {response && (
                <>
                  <div>
                    <dt>Flight action</dt>
                    <dd>{states.flight === 'unreported' ? 'Not reported' : states.flight}</dd>
                  </div>
                  <div>
                    <dt>Hotel action</dt>
                    <dd>{states.hotel === 'unreported' ? 'Not reported' : states.hotel}</dd>
                  </div>
                  <div>
                    <dt>Payment action</dt>
                    <dd>{states.payment === 'unreported' ? 'Not reported' : states.payment}</dd>
                  </div>
                  <div>
                    <dt>Compensations</dt>
                    <dd>{response.compensations_executed.length} reported</dd>
                  </div>
                </>
              )}
            </dl>
            {response?.error_message && (
              <div className="gateway-error">
                <strong>Gateway error</strong>
                <p>{response.error_message}</p>
              </div>
            )}
            <div className="result-note">
              <Icon name={run.phase === 'unknown' ? 'alert' : 'shield'} />
              <p>
                The total is the attempted booking amount, not a live account balance or proof of
                payment. No receipt or ticket ID is exposed by this API.
              </p>
            </div>
            <button
              className={`btn ${response?.status === 'CONFIRMED' ? 'btn-primary' : 'btn-ghost'} mt-4`}
              onClick={download}
            >
              <Icon name="download" />
              {response?.status === 'CONFIRMED'
                ? 'Download booking summary'
                : 'Download experiment report'}
            </button>
          </>
        )}
      </div>
    </aside>
  );
}

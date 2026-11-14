import { motion } from 'motion/react';
import { toast } from 'sonner';

import type { BookingRun } from '../lib/booking';
import { getStepLabel } from '../lib/booking';
import { formatDuration, formatTime } from '../lib/format';
import { Icon } from './Icon';

export function ExecutionSummary({
  run,
  elapsed,
  isPlaybackActive = false,
}: {
  run: BookingRun;
  elapsed: number | null;
  isPlaybackActive?: boolean;
}) {
  const response = run.phase === 'result' ? run.response : null;
  const bookingId = response?.booking_id || run.request.booking_id;

  async function copyId() {
    try {
      await navigator.clipboard.writeText(bookingId);
      toast.success('Booking ID copied to clipboard');
    } catch {
      toast.error('Could not copy automatically. Select the booking ID to copy it manually.');
    }
  }

  const isTest = typeof import.meta !== 'undefined' && import.meta.env?.MODE === 'test';

  return (
    <section className="execution-card card" aria-label="Execution summary">
      <div className="execution-header">
        <div>
          <h2>Execution summary</h2>
          <p>
            Reported action order · <span className="font-mono">{bookingId}</span>
          </p>
        </div>
        <button
          className="icon-button"
          aria-label="Copy booking ID"
          title="Copy booking ID"
          onClick={() => void copyId()}
        >
          <Icon name="copy" />
        </button>
      </div>

      {response && !isPlaybackActive ? (
        <>
          {response.steps_completed.length ? (
            <ol className="execution-list" aria-label="Completed actions">
              {response.steps_completed.map((step, index) => (
                <motion.li
                  className="execution-row"
                  key={`${step}-${index}`}
                  data-tone="mint"
                  initial={isTest ? false : { opacity: 0, x: -6 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.22, delay: index * 0.04 }}
                >
                  <span className="execution-rail" aria-hidden="true">
                    <span />
                  </span>
                  <span className="execution-index">{String(index + 1).padStart(2, '0')}</span>
                  <span>
                    <strong>{getStepLabel(step)}</strong>
                    <small>{step}</small>
                  </span>
                  <span className="execution-tag">COMPLETED</span>
                </motion.li>
              ))}
            </ol>
          ) : (
            <p className="execution-empty">No completed actions were reported.</p>
          )}

          {response.compensations_executed.length > 0 && (
            <>
              <div className="compensation-heading">
                <span>LIFO compensation</span>
                <small>reported execution order</small>
              </div>
              <ol className="execution-list" aria-label="Executed compensations">
                {response.compensations_executed.map((step, index) => (
                  <motion.li
                    className="execution-row"
                    key={`${step}-${index}`}
                    data-tone="coral"
                    initial={isTest ? false : { opacity: 0, x: 6 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ duration: 0.22, delay: index * 0.05 }}
                  >
                    <span className="execution-rail" aria-hidden="true">
                      <span />
                    </span>
                    <span className="execution-index">{String(index + 1).padStart(2, '0')}</span>
                    <span>
                      <strong>{getStepLabel(step)}</strong>
                      <small>{step}</small>
                    </span>
                    <span className="execution-tag">EXECUTED</span>
                  </motion.li>
                ))}
              </ol>
            </>
          )}
          <p className="execution-disclaimer">
            Per-step timestamps and durations are not included in the gateway response.{' '}
            {run.request.orchestrator === 'naive'
              ? 'The in-memory engine has no durable execution history; review reported errors and service state.'
              : 'Open Temporal for the full history.'}
          </p>
        </>
      ) : (
        <div className="execution-waiting">
          <span
            className={run.phase === 'pending' ? 'waiting-spinner' : 'waiting-icon'}
            aria-hidden="true"
          >
            {run.phase !== 'pending' && '?'}
          </span>
          <h3>
            {run.phase === 'pending' ? 'Awaiting gateway result' : 'No execution summary available'}
          </h3>
          <p>
            {run.phase === 'pending'
              ? 'The Saga is running. Its completed actions and compensations will appear when the gateway responds.'
              : 'No completed actions or compensations are assumed without a gateway result.'}
          </p>
        </div>
      )}
      <div className="execution-footer">
        <span>
          Submitted <span className="font-mono">{formatTime(run.startedAt)}</span>
        </span>
        <span className="font-mono">
          {formatDuration(elapsed)}
          {elapsed == null ? '' : ' · browser request'}
        </span>
      </div>
    </section>
  );
}

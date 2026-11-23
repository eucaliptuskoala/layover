import { useEffect, useState } from 'react';
import { toast } from 'sonner';

import type { BookingAuditReport, ServiceAuditRecord } from '../api/contracts';
import { getBookingAudit } from '../api/gateway';
import type { BookingRun } from '../lib/booking';
import { Icon } from './Icon';

interface DatabaseAuditCardProps {
  run: BookingRun;
  isPlaybackActive?: boolean;
}

function ServiceDbCard({
  service,
}: {
  service: ServiceAuditRecord;
}) {
  const isStranded = service.is_stranded;
  const isNotFound = service.status === 'NOT_FOUND';
  const isConfirmed = service.status === 'CONFIRMED' || service.status === 'CHARGED';
  const isRolledBack = service.status === 'CANCELLED' || service.status === 'REFUNDED';

  const dotTone = isStranded ? 'amber' : isConfirmed ? '' : 'neutral';

  const statusClass = isStranded
    ? 'status-stranded'
    : isConfirmed
      ? 'status-confirmed'
      : isRolledBack
        ? 'status-rolled-back'
        : '';

  return (
    <div
      className={`db-service-item card ${isStranded ? 'db-item-stranded' : isNotFound ? 'db-item-empty' : 'db-item-active'
        }`}
    >
      <div className="db-service-header">
        <div className="flex items-center gap-1.5 min-w-0">
          <span className={`status-dot ${dotTone}`} />
          <strong className="truncate text-xs font-semibold">{service.database_file}</strong>
        </div>
        <span className={`db-status-pill ${statusClass}`}>
          {service.status}
        </span>
      </div>

      <p className="db-service-name text-[10px] text-muted">{service.service_name}</p>

      <p className="db-service-message text-[11px] leading-relaxed mt-1">
        {service.message}
      </p>
    </div>
  );
}

export function DatabaseAuditCard({
  run,
  isPlaybackActive = false,
}: DatabaseAuditCardProps) {
  const response = run.phase === 'result' ? run.response : null;
  const bookingId = response?.booking_id || run.request.booking_id;

  const [refetchedAudit, setRefetchedAudit] = useState<BookingAuditReport | null>(null);
  const [prevBookingId, setPrevBookingId] = useState(bookingId);
  const [isLoading, setIsLoading] = useState(false);

  let currentRefetched = refetchedAudit;
  if (bookingId !== prevBookingId) {
    setPrevBookingId(bookingId);
    setRefetchedAudit(null);
    currentRefetched = null;
  }

  const audit = currentRefetched ?? response?.audit ?? null;

  useEffect(() => {
    if (response?.audit) {
      return;
    }

    if (run.phase !== 'pending' && !isPlaybackActive && bookingId) {
      setIsLoading(true);
      getBookingAudit(bookingId)
        .then((data) => setRefetchedAudit(data))
        .catch(() => setRefetchedAudit(null))
        .finally(() => setIsLoading(false));
    }
  }, [response?.audit, bookingId, run.phase, isPlaybackActive]);

  async function handleRefresh() {
    if (!bookingId || isLoading) return;
    setIsLoading(true);
    try {
      const data = await getBookingAudit(bookingId);
      setRefetchedAudit(data);
      toast.success('Database state audit updated');
    } catch {
      toast.error('Could not refresh database state audit');
    } finally {
      setIsLoading(false);
    }
  }

  const isPending = run.phase === 'pending' || isPlaybackActive;

  return (
    <section className="database-audit-card card" aria-label="Distributed database audit">
      <div className="audit-card-header">
        <div>
          <div className="flex items-center gap-2">
            <h2>Database state audit</h2>
            {audit && !isPending && (
              <span
                className={`audit-status-badge ${audit.has_stranded_records ? 'badge-stranded' : 'badge-consistent'
                  }`}
              >
                <span className={`status-dot ${audit.has_stranded_records ? 'amber' : ''}`} />
                {audit.has_stranded_records ? 'Stranded Holds Detected' : 'Consistent State'}
              </span>
            )}
          </div>
          <p>
            Independent SQLite verification · <span className="font-mono">{bookingId}</span>
          </p>
        </div>

        <button
          className="icon-button"
          onClick={() => void handleRefresh()}
          disabled={isLoading || isPending}
          aria-label="Refresh database audit"
          title="Re-probe microservice databases via HTTP"
        >
          <Icon name="refresh" className={isLoading ? 'spin' : ''} />
        </button>
      </div>

      <div className="audit-card-body">
        {isPending ? (
          <div className="audit-waiting">
            <span className="waiting-spinner" aria-hidden="true" />
            <p>Awaiting transaction outcome before verifying database states...</p>
          </div>
        ) : audit ? (
          <div className="db-services-grid">
            <ServiceDbCard service={audit.flight} />
            <ServiceDbCard service={audit.hotel} />
            <ServiceDbCard service={audit.payment} />
          </div>
        ) : (
          <div className="audit-empty">
            <p>Database state audit is currently unavailable for this booking.</p>
          </div>
        )}
      </div>
    </section>
  );
}

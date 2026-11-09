import type { BookingResponse, HealthReport, Orchestrator } from '../api/contracts';
import type { NodeVisualState, TopologyPlayback } from '../hooks/useTopologyPlayback';
import { getServiceStates, type ServiceState } from '../lib/booking';
import { formatDuration, getServiceAddress } from '../lib/format';
import { Icon } from './Icon';

const SERVICES = [
  {
    key: 'flight',
    name: 'Flight',
    healthName: 'Flight Service',
    icon: 'plane',
    action: 'reserve · confirm · cancel',
  },
  {
    key: 'hotel',
    name: 'Hotel',
    healthName: 'Hotel Service',
    icon: 'hotel',
    action: 'reserve · confirm · cancel',
  },
  {
    key: 'payment',
    name: 'Payment',
    healthName: 'Payment Service',
    icon: 'card',
    action: 'charge · refund',
  },
] as const;

function fallbackState(state: ServiceState): NodeVisualState {
  if (state === 'confirmed' || state === 'reserved' || state === 'charged') return 'ok';
  if (state === 'cancelled' || state === 'refunded') return 'cancel';
  if (state === 'unreported') return 'skip';
  return 'idle';
}

export function ServiceTopology({
  response,
  isPending,
  elapsed,
  health,
  orchestrator,
  playback,
}: {
  response: BookingResponse | null;
  isPending: boolean;
  elapsed: number | null;
  health: HealthReport | null;
  orchestrator: Orchestrator;
  playback?: TopologyPlayback;
}) {
  const states = getServiceStates(response);

  return (
    <section className="topology-card card" aria-label="Booking service topology">
      <div className="topology-header">
        <h2>
          Service topology{' '}
          <span>
            Engine: {orchestrator === 'naive' ? 'In-memory (baseline)' : 'Temporal (durable)'}
          </span>
        </h2>
        <span className="text-[11px] text-muted">
          <b className="font-mono text-ink">{formatDuration(elapsed)}</b> browser request
        </span>
      </div>

      <div className="topology-nodes">
        {SERVICES.map((service, index) => {
          const nodeVisual = playback?.nodes[service.key];
          const visualState =
            nodeVisual?.state ||
            (isPending
              ? 'running'
              : response
                ? fallbackState(states[service.key])
                : 'idle');
          const badgeText =
            nodeVisual?.badge ||
            (isPending
              ? 'awaiting result'
              : response
                ? states[service.key] === 'unreported'
                  ? 'not reported'
                  : states[service.key]
                : 'unknown');
          const subText = nodeVisual?.sub || service.action;
          const link = index > 0 && playback ? playback.links[index - 1] : null;

          return (
            <div className="topology-segment" key={service.key}>
              {index > 0 && (
                <div
                  className={`topology-link ${
                    link?.isReverse ? 'is-reverse' : link?.isLive ? 'is-live' : ''
                  }`}
                  aria-hidden="true"
                >
                  <div className="topology-link-line" />
                  <div className="topology-link-dot" />
                </div>
              )}
              <div
                className="service-node"
                data-state={visualState}
              >
                <div className="flex items-center gap-2">
                  <span className="node-icon">
                    <Icon name={service.icon} />
                  </span>
                  <h3>{service.name}</h3>
                  <span className="node-address">
                    {health?.services.find((item) => item.name === service.healthName)?.url
                      ? getServiceAddress(
                          health.services.find((item) => item.name === service.healthName)!.url,
                        )
                      : 'service'}
                  </span>
                </div>
                <p className="node-action">{subText}</p>
                <span className="node-status">
                  <span className="status-dot" />
                  {badgeText}
                </span>
              </div>
            </div>
          );
        })}
      </div>

      <p className="topology-note">
        {isPending
          ? 'Dispatching multi-service Saga transaction across independent microservices.'
          : playback && !playback.isComplete
            ? 'Stepping through distributed saga state machine and compensations...'
            : 'States are derived from actions reported by the orchestrator and verified in SQLite.'}
      </p>
    </section>
  );
}


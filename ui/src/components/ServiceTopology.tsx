import type { BookingResponse, HealthReport } from '../api/contracts';
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

function stateTone(state: ServiceState) {
  return ['cancelled', 'refunded'].includes(state)
    ? 'coral'
    : ['confirmed', 'reserved', 'charged'].includes(state)
      ? 'mint'
      : 'neutral';
}

export function ServiceTopology({
  response,
  isPending,
  elapsed,
  health,
}: {
  response: BookingResponse | null;
  isPending: boolean;
  elapsed: number | null;
  health: HealthReport | null;
}) {
  const states = getServiceStates(response);
  return (
    <section className="topology-card card" aria-label="Booking service topology">
      <div className="topology-header">
        <h2>
          Service topology <span>3 services · 1 orchestrator</span>
        </h2>
        <span className="text-[11px] text-muted">
          <b className="font-mono text-ink">{formatDuration(elapsed)}</b> browser request
        </span>
      </div>
      <div className="topology-nodes">
        {SERVICES.map((service, index) => (
          <div className="topology-segment" key={service.key}>
            {index > 0 && <div className="topology-connector" aria-hidden="true" />}
            <div
              className="service-node"
              data-tone={response ? stateTone(states[service.key]) : 'neutral'}
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
              <p className="node-action">{service.action}</p>
              <span className="node-status">
                <span className="status-dot" />
                {isPending
                  ? 'awaiting result'
                  : response
                    ? states[service.key] === 'unreported'
                      ? 'not reported'
                      : states[service.key]
                    : 'unknown'}
              </span>
            </div>
          </div>
        ))}
      </div>
      <p className="topology-note">
        {isPending
          ? 'The gateway waits for the full workflow. Individual activity progress is not exposed.'
          : 'States are derived only from the actions reported by the gateway, not direct database reads.'}
      </p>
    </section>
  );
}

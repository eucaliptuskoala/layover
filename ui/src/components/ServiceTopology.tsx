import { motion } from 'motion/react';

import type { BookingResponse, HealthReport, Orchestrator } from '../api/contracts';
import type { NodeVisualState, TopologyPlayback } from '../hooks/useTopologyPlayback';
import { formatDuration, getServiceAddress } from '../lib/format';
import { AnimatedBeam } from './AnimatedBeam';
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

export function ServiceTopology({
  isPending,
  elapsed,
  health,
  orchestrator,
  playback,
}: {
  response?: BookingResponse | null;
  isPending: boolean;
  elapsed: number | null;
  health: HealthReport | null;
  orchestrator: Orchestrator;
  playback?: TopologyPlayback;
}) {
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
          const visualState: NodeVisualState =
            nodeVisual?.state || (isPending ? 'running' : 'idle');
          const badgeText =
            nodeVisual?.badge || (isPending ? 'awaiting result' : 'idle');
          const subText = nodeVisual?.sub || service.action;
          const link = index > 0 && playback ? playback.links[index - 1] : null;

          const serviceItem = health?.services.find((item) => item.name === service.healthName);
          const address = serviceItem?.url ? getServiceAddress(serviceItem.url) : 'service';

          return (
            <div className="topology-segment" key={service.key}>
              {index > 0 && (
                <AnimatedBeam
                  isLive={!!link?.isLive}
                  isReverse={!!link?.isReverse}
                />
              )}
              <motion.div
                className="service-node"
                data-state={visualState}
                animate={
                  visualState === 'err'
                    ? { x: [0, -4, 4, -3, 3, 0], transition: { duration: 0.34 } }
                    : visualState === 'unwinding'
                      ? { x: [0, -3, 3, -2, 2, 0], transition: { duration: 0.34 } }
                      : visualState === 'running'
                        ? { scale: [1, 1.012, 1], transition: { repeat: Infinity, duration: 1.2 } }
                        : { x: 0, scale: 1 }
                }
              >
                <div className="flex items-center gap-2">
                  <span className="node-icon">
                    <Icon name={service.icon} />
                  </span>
                  <h3>{service.name}</h3>
                  <span className="node-address">{address}</span>
                </div>
                <p className="node-action">{subText}</p>
                <span className="node-status">
                  <span className="status-dot" />
                  {badgeText}
                </span>
              </motion.div>
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


import { useState } from 'react';

import {
  isScenarioKey,
  type HealthReport,
  type Orchestrator,
  type Scenario,
  type ScenarioKey,
} from '../api/contracts';
import type { Resource } from '../hooks/useResource';
import { formatTime, getServiceAddress } from '../lib/format';
import { Icon } from './Icon';

const SCENARIO_LABELS: Record<string, { name: string; hint: string }> = {
  happy_path: { name: 'Happy path', hint: 'all steps complete' },
  fail_payment: { name: 'Payment decline', hint: '400 · LIFO rollback' },
  fail_hotel: { name: 'Hotel rejection', hint: '422 · partial rollback' },
  slow_demo: { name: 'Chaos pause (4s)', hint: 'manual crash window' },
};

export function SandboxPanel({
  scenarios,
  selectedKey,
  onSelect,
  selectedOrchestrator,
  onSelectOrchestrator,
  health,
  isOpen,
  onToggle,
  isDisabled,
}: {
  scenarios: Scenario[];
  selectedKey: ScenarioKey;
  onSelect: (key: ScenarioKey) => void;
  selectedOrchestrator: Orchestrator;
  onSelectOrchestrator: (orchestrator: Orchestrator) => void;
  health: Resource<HealthReport>;
  isOpen: boolean;
  onToggle: () => void;
  isDisabled: boolean;
}) {
  const [isHealthOpen, setHealthOpen] = useState(false);
  const selected = scenarios.find((scenario) => scenario.key === selectedKey);
  const healthyCount =
    health.data?.services.filter((service) => service.status === 'UP').length || 0;
  const healthLabel =
    health.status === 'loading'
      ? 'Checking health'
      : health.status === 'error'
        ? 'Health unavailable'
        : `${healthyCount}/${health.data?.services.length || 0} healthy`;
  const tone =
    health.status !== 'success'
      ? 'neutral'
      : health.data?.overall_status === 'HEALTHY'
        ? 'mint'
        : 'amber';

  function toggleHealth() {
    if (!isOpen) onToggle();
    setHealthOpen((previous) => !previous);
  }

  return (
    <aside className="sandbox" aria-label="Sandbox controls" data-open={isOpen}>
      <div className="sandbox-top">
        <span className="sandbox-brand">
          <span className="status-dot amber" />
          Sandbox
        </span>
        <button
          className="health-button"
          data-tone={tone}
          onClick={toggleHealth}
          aria-expanded={isOpen && isHealthOpen}
          aria-controls="cluster-health"
        >
          <span className="status-dot" />
          {healthLabel}
          <Icon name="down" />
        </button>
        <button
          className="icon-button"
          onClick={onToggle}
          aria-expanded={isOpen}
          aria-controls="sandbox-body"
          aria-label={isOpen ? 'Collapse sandbox controls' : 'Expand sandbox controls'}
        >
          <Icon name={isOpen ? 'up' : 'down'} />
        </button>
      </div>

      <div id="sandbox-body" className="sandbox-body" hidden={!isOpen}>
        {isHealthOpen && (
          <section id="cluster-health" className="health-panel" aria-label="Cluster health">
            <div className="flex items-center justify-between gap-2">
              <h2 className="eyebrow">Cluster health</h2>
              <button
                className="icon-button"
                onClick={health.refresh}
                disabled={health.status === 'loading'}
                aria-label="Refresh health"
                title="Refresh health"
              >
                <Icon name="refresh" className={health.status === 'loading' ? 'spin' : undefined} />
              </button>
            </div>
            {health.status === 'error' ? (
              <p className="text-xs text-rose-700 leading-relaxed">{health.error}</p>
            ) : health.data ? (
              <>
                <div className="service-health-grid">
                  {health.data.services.map((service) => (
                    <div className="service-health" key={service.name}>
                      <span className="flex items-center gap-1.5 font-semibold">
                        <span className={`status-dot ${service.status === 'UP' ? '' : 'rose'}`} />
                        {service.name.replace(' Service', '').replace(' Engine', '')}
                        <span className="ml-auto font-mono text-[10px] text-muted">
                          {service.status}
                        </span>
                      </span>
                      <span className="font-mono text-[10px] text-muted break-words">
                        {getServiceAddress(service.url)} ·{' '}
                        {service.latency_ms == null
                          ? 'no timing'
                          : `${service.latency_ms.toFixed(1)} ms`}
                      </span>
                      {service.error && (
                        <span className="text-[10px] text-rose-700 break-words">
                          {service.error}
                        </span>
                      )}
                    </div>
                  ))}
                </div>
                <p className="mt-2 text-[10px] text-muted">
                  {health.updatedAt && `Checked ${formatTime(health.updatedAt)} · `}on-demand probe,
                  not continuous monitoring
                </p>
              </>
            ) : (
              <p className="text-xs text-muted">Contacting the gateway…</p>
            )}
          </section>
        )}

        <fieldset className="sandbox-group">
          <legend className="eyebrow mb-2">Orchestrator</legend>
          <div className="engine-options">
            <label
              className={`engine-option ${selectedOrchestrator === 'naive' ? 'selected' : ''}`}
            >
              <input
                type="radio"
                name="orchestrator"
                value="naive"
                checked={selectedOrchestrator === 'naive'}
                disabled={isDisabled}
                onChange={() => onSelectOrchestrator('naive')}
              />
              <span>
                In-memory <em>baseline</em>
              </span>
            </label>
            <label
              className={`engine-option ${selectedOrchestrator === 'temporal' ? 'selected' : ''}`}
            >
              <input
                type="radio"
                name="orchestrator"
                value="temporal"
                checked={selectedOrchestrator === 'temporal'}
                disabled={isDisabled}
                onChange={() => onSelectOrchestrator('temporal')}
              />
              <span>
                Temporal <em>durable</em>
              </span>
            </label>
          </div>
        </fieldset>

        <fieldset className="sandbox-group">
          <legend className="sandbox-legend">
            <span className="eyebrow">Scenario</span>
            <span className={`expected-outcome ${selectedKey === 'happy_path' ? '' : 'failure'}`}>
              expect {selectedKey === 'happy_path' ? 'CONFIRMED' : 'COMPENSATED'}
            </span>
          </legend>
          <div className="scenario-grid">
            {scenarios.map((scenario) => (
              <label
                key={scenario.key}
                className="scenario-option"
                data-selected={scenario.key === selectedKey}
                data-fault={scenario.key !== 'happy_path'}
              >
                <input
                  type="radio"
                  name="scenario"
                  value={scenario.key}
                  checked={scenario.key === selectedKey}
                  disabled={isDisabled || !isScenarioKey(scenario.key)}
                  onChange={() => {
                    if (isScenarioKey(scenario.key)) onSelect(scenario.key);
                  }}
                />
                <span>{SCENARIO_LABELS[scenario.key]?.name || scenario.name}</span>
                <em>{SCENARIO_LABELS[scenario.key]?.hint || 'gateway scenario'}</em>
              </label>
            ))}
          </div>
        </fieldset>

        <p className="sandbox-note">
          {selected?.description || 'Choose a gateway scenario to run a booking experiment.'}
        </p>
        <p className="sandbox-note text-[10px]">
          {selectedOrchestrator === 'naive'
            ? 'In-memory: single HTTP attempts and volatile rollback state. Process crash destroys compensation stack.'
            : 'Temporal: durable workflow history and activity retries. Recovers automatically upon worker restart.'}{' '}
          Simulate container crashes via docker kill during Chaos pause.
        </p>
      </div>
    </aside>
  );
}

import { describe, expect, it } from 'vitest';

import { readRun, readScenario, saveRun, saveScenario } from '../src/lib/storage';
import { confirmedResponse, scenarios } from './fixtures';

describe('sandbox persistence', () => {
  it('remembers a valid scenario and ignores unsupported or corrupted preferences', () => {
    saveScenario('fail_payment');
    expect(readScenario()).toBe('fail_payment');

    localStorage.setItem('layover.ui.scenario.v1', 'chaos');
    expect(readScenario()).toBe('happy_path');
  });

  it('restores a pending request as unknown, never as a request to submit again', () => {
    saveRun({
      phase: 'pending',
      request: { booking_id: 'bk-test', orchestrator: 'temporal', scenario: 'happy_path' },
      scenario: scenarios[0]!,
      startedAt: Date.now(),
    });

    expect(readRun()).toMatchObject({ phase: 'unknown', request: { booking_id: 'bk-test' } });
  });

  it('preserves completed gateway results across a refresh', () => {
    saveRun({
      phase: 'result',
      request: { booking_id: 'bk-test', orchestrator: 'temporal', scenario: 'happy_path' },
      scenario: scenarios[0]!,
      startedAt: Date.now(),
      durationMs: 132,
      response: confirmedResponse,
    });

    expect(readRun()).toMatchObject({ phase: 'result', response: confirmedResponse });
  });

  it('ignores malformed stored runs and future unsupported data', () => {
    sessionStorage.setItem('layover.ui.run.v1', '{bad json');
    expect(readRun()).toBeNull();

    sessionStorage.setItem('layover.ui.run.v1', JSON.stringify({ phase: 'result', response: {} }));
    expect(readRun()).toBeNull();
  });

  it('restores a pending naive request with engine-appropriate reconciliation guidance', () => {
    saveRun({
      phase: 'pending',
      request: { booking_id: 'bk-naive', orchestrator: 'naive', scenario: 'happy_path' },
      scenario: scenarios[0]!,
      startedAt: Date.now(),
    });

    const run = readRun();
    expect(run).toMatchObject({ phase: 'unknown', request: { orchestrator: 'naive' } });
    if (run?.phase !== 'unknown') throw new Error('Expected an unknown run');
    expect(run.message).toContain('does not recover automatically');
    expect(run.message).not.toContain('Temporal');
  });
});

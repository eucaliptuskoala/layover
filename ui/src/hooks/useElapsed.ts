import { useEffect, useState } from 'react';

import type { BookingRun } from '../lib/booking';

export function useElapsed(run: BookingRun | null): number | null {
  const [now, setNow] = useState(Date.now);
  const isPending = run?.phase === 'pending';

  useEffect(() => {
    if (!isPending) return;
    const timer = window.setInterval(() => setNow(Date.now()), 250);
    return () => window.clearInterval(timer);
  }, [isPending]);

  if (!run) return null;
  return run.phase === 'pending' ? Math.max(0, now - run.startedAt) : (run.durationMs ?? null);
}

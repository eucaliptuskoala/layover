import { useCallback, useEffect, useState } from 'react';

import { getErrorMessage } from '../api/gateway';

export interface Resource<T> {
  status: 'loading' | 'success' | 'error';
  data: T | null;
  error: string | null;
  updatedAt: number | null;
  refresh: () => void;
}

export function useResource<T>(load: (signal?: AbortSignal) => Promise<T>): Resource<T> {
  const [revision, setRevision] = useState(0);
  const [resource, setResource] = useState<Omit<Resource<T>, 'refresh'>>({
    status: 'loading',
    data: null,
    error: null,
    updatedAt: null,
  });

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) {
          setResource({ status: 'success', data, error: null, updatedAt: Date.now() });
        }
      },
      (error: unknown) => {
        if (!controller.signal.aborted) {
          setResource((previous) => ({
            ...previous,
            status: 'error',
            error: getErrorMessage(error),
          }));
        }
      },
    );
    return () => controller.abort();
  }, [load, revision]);

  const refresh = useCallback(() => {
    setResource((previous) => ({ ...previous, status: 'loading', error: null }));
    setRevision((previous) => previous + 1);
  }, []);

  return { ...resource, refresh };
}

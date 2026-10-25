"use client";

/**
 * useApiQuery — load data from a service function with loading/error state.
 *
 *   const { data, error, loading, reload } = useApiQuery((signal) => getMudra(id, signal), [id]);
 *
 * How it works: every combination of inputs gets a "key". When a request
 * finishes, we store its result together with the key it was made for.
 * `loading` is simply "the latest settled key is not the current key".
 * The request is cancelled when the inputs change or the component unmounts,
 * so a slow old response can never overwrite a newer one.
 *
 * `deps` must be primitives (ids, strings) — they are used to build the key.
 */
import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/types/api";

export interface ApiQueryState<T> {
  /** Latest successfully loaded data (kept while a reload is in flight). */
  data: T | null;
  error: unknown;
  loading: boolean;
  reload: () => void;
}

interface Settled<T> {
  key: string | null;
  data: T | null;
  error: unknown;
}

export function useApiQuery<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  deps: ReadonlyArray<string | number | boolean | null | undefined>,
  enabled = true,
): ApiQueryState<T> {
  const [version, setVersion] = useState(0);
  const [settled, setSettled] = useState<Settled<T>>({ key: null, data: null, error: null });
  const reload = useCallback(() => setVersion((v) => v + 1), []);

  const key = JSON.stringify([...deps, version]);

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    fetcher(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setSettled({ key, data, error: null });
      })
      .catch((error) => {
        if (controller.signal.aborted || (error instanceof ApiError && error.kind === "aborted")) return;
        setSettled((prev) => ({ key, data: prev.data, error }));
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `key` captures deps + reloads; fetcher is recreated every render
  }, [key, enabled]);

  const isCurrent = settled.key === key;
  return {
    data: settled.data,
    error: isCurrent ? settled.error : null,
    loading: enabled && !isCurrent,
    reload,
  };
}

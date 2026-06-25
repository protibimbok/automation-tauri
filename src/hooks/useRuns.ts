import { useCallback, useEffect, useState } from "react";

import {
  RunsApi,
  type RunControlAction,
  type RunEvent,
  type RunInfo,
  type RunInput,
  type RunItem,
  type RunLogPayload,
  type RunStatusPayload,
} from "@/lib/runs";

function applyStatus(runs: RunInfo[], payload: RunStatusPayload): RunInfo[] {
  return runs.map((run) =>
    run.id === payload.run_id
      ? {
          ...run,
          status: payload.status,
          error: payload.error ?? run.error,
          pause_info:
            payload.pause_info !== undefined
              ? payload.pause_info
              : run.pause_info,
        }
      : run,
  );
}

export function useRuns(platform?: string) {
  const [runs, setRuns] = useState<RunInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [pendingRunId, setPendingRunId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      const rows = await RunsApi.list(platform);
      setRuns(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [platform]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const onEvent = (event: RunEvent) => {
      const { route, payload } = event;
      if (!payload || !("run_id" in payload)) return;

      if (route === "task.status") {
        const status = payload as RunStatusPayload;
        setRuns((prev) => {
          const known = prev.some((run) => run.id === status.run_id);
          if (!known) {
            // A run we don't have yet (e.g. just started) — pull the full list.
            void refresh();
            return prev;
          }
          return applyStatus(prev, status);
        });
      } else if (route === "task.item") {
        const item = payload as RunItem;
        if (!item.id) return;
        setRuns((prev) =>
          prev.map((run) =>
            run.id === item.run_id
              ? { ...run, item_count: run.item_count + 1 }
              : run,
          ),
        );
      }
    };

    void RunsApi.subscribe(onEvent);
    return () => RunsApi.unsubscribe(onEvent);
  }, [refresh]);

  const runAction = useCallback(
    async (runId: string, fn: () => Promise<RunInfo | void>) => {
      setPendingRunId(runId);
      setError(null);
      try {
        const updated = await fn();
        if (updated) {
          setRuns((prev) =>
            prev.map((run) => (run.id === runId ? updated : run)),
          );
        }
        return updated ?? null;
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        return null;
      } finally {
        setPendingRunId(null);
      }
    },
    [],
  );

  const control = useCallback(
    (runId: string, action: RunControlAction) =>
      runAction(runId, () => RunsApi.control(runId, action)),
    [runAction],
  );

  const restart = useCallback(
    (runId: string) => runAction(runId, () => RunsApi.restart(runId)),
    [runAction],
  );

  const remove = useCallback(
    async (runId: string) => {
      setPendingRunId(runId);
      setError(null);
      try {
        await RunsApi.delete(runId);
        setRuns((prev) => prev.filter((run) => run.id !== runId));
        return true;
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        return false;
      } finally {
        setPendingRunId(null);
      }
    },
    [],
  );

  const clearError = useCallback(() => setError(null), []);

  return {
    runs,
    error,
    pendingRunId,
    refresh,
    control,
    restart,
    remove,
    clearError,
  };
}

const MAX_LOG_LINES = 500;

/** Seeds a run's stored log then streams live `task.log` lines for it. */
export function useRunLog(runId: string | null) {
  const [lines, setLines] = useState<string[]>([]);

  useEffect(() => {
    let active = true;
    setLines([]);
    if (!runId) return;

    void RunsApi.get(runId)
      .then((run) => {
        if (!active) return;
        setLines(run.log ? run.log.split("\n") : []);
      })
      .catch(() => {
        /* ignore transient errors */
      });

    return () => {
      active = false;
    };
  }, [runId]);

  useEffect(() => {
    if (!runId) return;

    const onEvent = (event: RunEvent) => {
      if (event.route !== "task.log") return;
      const payload = event.payload as RunLogPayload;
      if (payload.run_id !== runId) return;
      setLines((prev) => [...prev.slice(-(MAX_LOG_LINES - 1)), payload.line]);
    };

    void RunsApi.subscribe(onEvent);
    return () => RunsApi.unsubscribe(onEvent);
  }, [runId]);

  return lines;
}

/** Loads the inputs (profiles) for a run. */
export function useRunInputs(runId: string) {
  const [inputs, setInputs] = useState<RunInput[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!runId) return;
    setLoading(true);
    setError(null);
    try {
      setInputs(await RunsApi.inputs(runId));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [runId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { inputs, loading, error, refresh };
}

function sortItems(items: RunItem[]) {
  return [...items].sort((a, b) => a.ordinal - b.ordinal);
}

/** Loads run items from DB and appends rows as `task.item` events arrive for `runId`. */
export function useRunItems(runId: string, inputId?: string | null) {
  const [items, setItems] = useState<RunItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const rows = await RunsApi.items(runId, inputId ?? undefined);
      setItems(sortItems(rows));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [runId, inputId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    const onEvent = (event: RunEvent) => {
      if (event.route !== "task.item") return;
      const item = event.payload as RunItem;
      if (item.run_id !== runId || !item.id) return;
      if (inputId && item.input_id !== inputId) return;
      setItems((prev) => {
        if (prev.some((row) => row.id === item.id)) return prev;
        return sortItems([...prev, item]);
      });
    };

    void RunsApi.subscribe(onEvent);
    return () => RunsApi.unsubscribe(onEvent);
  }, [runId, inputId]);

  return { items, loading, error, refresh };
}

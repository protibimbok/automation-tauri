import { useCallback, useEffect, useState } from "react";

import { SessionsApi, type SessionEvent } from "./api";
import { applySessionLiveRun, liveRunsFromInstances } from "./liveRuns";
import type { PlatformSlug } from "./platforms";
import {
  DEFAULT_CHROME_SESSION_ID,
  type SessionInfo,
  type SessionLiveRun,
} from "./types";

type PendingAction =
  | "create"
  | "create_default"
  | "launch"
  | "check"
  | "sync"
  | "stop"
  | "delete"
  | null;

export function useSessions(platform: PlatformSlug | undefined) {
  const [items, setItems] = useState<SessionInfo[]>([]);
  const [liveRuns, setLiveRuns] = useState<Record<string, SessionLiveRun>>({});
  const [pending, setPending] = useState<PendingAction>(null);
  const [pendingSessionId, setPendingSessionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [lastCheck, setLastCheck] = useState<
    Record<string, { logged_in: boolean; url: string }>
  >({});

  const refresh = useCallback(async () => {
    if (!platform) return;
    setError(null);
    try {
      const rows = await SessionsApi.list(platform);
      setItems(rows);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [platform]);

  const syncLiveStatus = useCallback(async () => {
    if (!platform) return;
    try {
      const result = await SessionsApi.status(platform);
      setLiveRuns(liveRunsFromInstances(result.instances));
      setItems(result.sessions);
    } catch {
      // ignore transient poll errors
    }
  }, [platform]);

  useEffect(() => {
    void refresh();
    void syncLiveStatus();
  }, [refresh, syncLiveStatus]);

  useEffect(() => {
    if (!platform) return;

    const onSession = (event: SessionEvent) => {
      if (event.route === "session.updated") {
        setLiveRuns((current) => applySessionLiveRun(current, event.payload));
        return;
      }
      if (event.route === "session.closed") {
        setLiveRuns((current) => {
          const next = { ...current };
          delete next[event.payload.session_id];
          return next;
        });
        void syncLiveStatus();
      }
    };

    void SessionsApi.subscribe(onSession);
    return () => SessionsApi.unsubscribe(onSession);
  }, [platform, syncLiveStatus]);

  const createSession = useCallback(
    async (name: string, launchFresh = true) => {
      if (!platform) return null;
      setPending("create");
      setError(null);
      try {
        const session = await SessionsApi.create(platform, name);
        if (launchFresh) {
          const launched = await SessionsApi.launch(session.id, true, platform);
          const created = launched.session;
          setItems((current) =>
            [...current, created].sort((a, b) => a.name.localeCompare(b.name)),
          );
          return created;
        }
        setItems((current) =>
          [...current, session].sort((a, b) => a.name.localeCompare(b.name)),
        );
        return session;
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        return null;
      } finally {
        setPending(null);
      }
    },
    [platform],
  );

  const addDefaultChrome = useCallback(async () => {
    if (!platform) return null;
    setPending("create_default");
    setError(null);
    try {
      const session = await SessionsApi.createDefault(platform);
      setItems((current) => {
        if (current.some((item) => item.id === DEFAULT_CHROME_SESSION_ID)) {
          return current;
        }
        return [session, ...current];
      });
      return session;
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      return null;
    } finally {
      setPending(null);
    }
  }, [platform]);

  const launchSession = useCallback(
    async (sessionId: string, fresh = false) => {
      setPending("launch");
      setPendingSessionId(sessionId);
      setError(null);
      try {
        const result = await SessionsApi.launch(sessionId, fresh, platform);
        setItems((current) =>
          current.map((item) =>
            item.id === result.session.id ? result.session : item,
          ),
        );
        return result.session;
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        return null;
      } finally {
        setPending(null);
        setPendingSessionId(null);
      }
    },
    [platform],
  );

  const stopSession = useCallback(
    async (sessionId: string) => {
      setPending("stop");
      setPendingSessionId(sessionId);
      setError(null);
      try {
        const result = await SessionsApi.stop(sessionId, platform);
        setItems((current) =>
          current.map((item) =>
            item.id === result.session.id ? result.session : item,
          ),
        );
        return result.session;
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        return null;
      } finally {
        setPending(null);
        setPendingSessionId(null);
      }
    },
    [platform],
  );

  const checkSession = useCallback(
    async (sessionId: string) => {
      setPending("check");
      setPendingSessionId(sessionId);
      setError(null);
      try {
        const result = await SessionsApi.check(sessionId, platform);
        setItems((current) =>
          current.map((item) =>
            item.id === result.session.id ? result.session : item,
          ),
        );
        setLastCheck((current) => ({
          ...current,
          [result.session.id]: {
            logged_in: result.logged_in,
            url: result.url,
          },
        }));
        return result;
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        return null;
      } finally {
        setPending(null);
        setPendingSessionId(null);
      }
    },
    [platform],
  );

  const syncSession = useCallback(
    async (sessionId: string) => {
      setPending("sync");
      setPendingSessionId(sessionId);
      setError(null);
      try {
        const result = await SessionsApi.sync(sessionId, platform);
        setItems((current) =>
          current.map((item) =>
            item.id === result.session.id ? result.session : item,
          ),
        );
        return result;
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        return null;
      } finally {
        setPending(null);
        setPendingSessionId(null);
      }
    },
    [platform],
  );

  const deleteSession = useCallback(async (sessionId: string) => {
    setPending("delete");
    setPendingSessionId(sessionId);
    setError(null);
    try {
      await SessionsApi.delete(sessionId);
      setItems((current) => current.filter((item) => item.id !== sessionId));
      setLiveRuns((current) => {
        const next = { ...current };
        delete next[sessionId];
        return next;
      });
      setLastCheck((current) => {
        const next = { ...current };
        delete next[sessionId];
        return next;
      });
      return true;
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      return false;
    } finally {
      setPending(null);
      setPendingSessionId(null);
    }
  }, []);

  const clearError = useCallback(() => setError(null), []);

  return {
    items,
    liveRuns,
    pending,
    pendingSessionId,
    error,
    lastCheck,
    refresh,
    syncLiveStatus,
    createSession,
    addDefaultChrome,
    launchSession,
    stopSession,
    checkSession,
    syncSession,
    deleteSession,
    clearError,
  };
}

export function usePlatformSessions(platform: PlatformSlug | undefined) {
  const state = useSessions(platform);
  return {
    sessions: state.items,
    ...state,
  };
}

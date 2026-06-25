import type { SessionLiveRun, SessionRunEventPayload } from "./types";

export function liveRunsFromInstances(
  instances: SessionLiveRun[],
): Record<string, SessionLiveRun> {
  const next: Record<string, SessionLiveRun> = {};
  for (const instance of instances) {
    if (instance.running) {
      next[instance.session_id] = instance;
    }
  }
  return next;
}

export function liveRunFromPayload(
  payload: SessionRunEventPayload,
): SessionLiveRun | null {
  if (!payload.running) {
    return null;
  }
  return {
    session_id: payload.session_id,
    run_id: payload.run_id,
    running: true,
    headless: payload.headless,
    url: payload.url,
  };
}

export function applySessionLiveRun(
  current: Record<string, SessionLiveRun>,
  payload: SessionRunEventPayload,
): Record<string, SessionLiveRun> {
  const next = { ...current };
  const live = liveRunFromPayload(payload);
  if (live) {
    next[payload.session_id] = live;
  } else {
    delete next[payload.session_id];
  }
  return next;
}

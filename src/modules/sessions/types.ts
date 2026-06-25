export type SessionStatus = "idle" | "running" | "error";

export const DEFAULT_CHROME_SESSION_ID = "default-chrome";

export type SessionInfo = {
  id: string;
  platform: string;
  name: string;
  status: SessionStatus;
  active_run_count: number;
  last_checked_at: string | null;
  created_at: string;
  updated_at: string;
  has_storage: boolean;
};

export function usesSystemProfile(session: Pick<SessionInfo, "id">): boolean {
  return session.id === DEFAULT_CHROME_SESSION_ID;
}

export type SessionLaunchResult = {
  session: SessionInfo;
  run_id: string;
  running: boolean;
  url: string;
};

export type SessionCheckResult = {
  session: SessionInfo;
  ok: boolean;
  logged_in: boolean;
  url: string;
  cookie_count: number;
};

export type StoredCookie = {
  name: string;
  domain: string;
  path: string;
  value: string;
  expires: number | null;
  http_only: boolean;
  secure: boolean;
  same_site: string;
};

export type SessionLiveRun = {
  session_id: string;
  run_id: string;
  running: boolean;
  headless: boolean;
  url: string;
};

export type SessionRunEventPayload = SessionLiveRun & {
  ok?: boolean;
  crashed?: boolean;
};

export type SessionStatusResult = {
  sessions: SessionInfo[];
  instances: SessionLiveRun[];
};

export type SessionSyncResult = {
  session: SessionInfo;
  ok: boolean;
  files_copied: number;
  cookie_count: number;
};

export type SessionStopResult = {
  session: SessionInfo;
  run_id: string;
  running: boolean;
};

export function isSessionBrowserOpen(
  session: Pick<SessionInfo, "id">,
  liveRuns: Record<string, SessionLiveRun>,
): boolean {
  return liveRuns[session.id]?.running === true;
}

export function sessionBrowserStatus(
  session: Pick<SessionInfo, "id">,
  liveRuns: Record<string, SessionLiveRun>,
): SessionStatus {
  return isSessionBrowserOpen(session, liveRuns) ? "running" : "idle";
}

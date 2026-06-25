import { Backend, type DaemonEvent } from "@/lib/api";

import type { PlatformSlug } from "./platforms";
import type {
  SessionCheckResult,
  SessionInfo,
  SessionLaunchResult,
  SessionRunEventPayload,
  SessionStatusResult,
  SessionStopResult,
  SessionSyncResult,
  StoredCookie,
} from "./types";

export type SessionEvent = DaemonEvent<SessionRunEventPayload>;

const CHANNEL = "session";

export class SessionsApi {
  static list(platform: PlatformSlug) {
    return Backend.request<SessionInfo[]>("sessions.list", { platform });
  }

  static create(platform: PlatformSlug, name: string) {
    return Backend.request<SessionInfo>("sessions.create", { platform, name });
  }

  static createDefault(platform: PlatformSlug) {
    return Backend.request<SessionInfo>("sessions.create_default", { platform });
  }

  static delete(sessionId: string) {
    return Backend.request<void>("sessions.delete", { session_id: sessionId });
  }

  static launch(sessionId: string, fresh = false, platform?: PlatformSlug) {
    return Backend.request<SessionLaunchResult>("sessions.launch", {
      session_id: sessionId,
      fresh,
      platform,
    });
  }

  static check(sessionId: string, platform?: PlatformSlug) {
    return Backend.request<SessionCheckResult>("sessions.check", {
      session_id: sessionId,
      platform,
    });
  }

  static sync(sessionId: string, platform?: PlatformSlug) {
    return Backend.request<SessionSyncResult>("sessions.sync", {
      session_id: sessionId,
      platform,
    });
  }

  static cookies(sessionId: string) {
    return Backend.request<StoredCookie[]>("sessions.cookies", {
      session_id: sessionId,
    });
  }

  static status(platform: PlatformSlug) {
    return Backend.request<SessionStatusResult>("sessions.status", { platform });
  }

  static stop(sessionId: string, platform?: PlatformSlug) {
    return Backend.request<SessionStopResult>("sessions.stop", {
      session_id: sessionId,
      platform,
    });
  }

  static subscribe(cb: (event: SessionEvent) => void) {
    return Backend.subscribeDaemon<SessionRunEventPayload>(CHANNEL, cb);
  }

  static unsubscribe(cb: (event: SessionEvent) => void) {
    Backend.unsubscribeDaemon(cb as never);
  }
}

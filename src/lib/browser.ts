import { Backend, type DaemonEvent } from "@/lib/api";

export type BrowserRun = {
  ok: boolean;
  run_id: string;
  running: boolean;
  headless: boolean;
  url: string;
  paused: boolean;
  crashed: boolean;
};

export type BrowserInstallResult = {
  ok: boolean;
  installed: boolean;
  error?: string;
};

export type BrowserInstallProgress = {
  message: string;
  percent?: number | null;
};

export type BrowserStatusResult =
  | BrowserRun
  | { ok: boolean; instances: BrowserRun[] };

export type BrowserEvent = DaemonEvent<BrowserRun>;

const CHANNEL = "browser";

function runPayload(runId: string, extra: Record<string, unknown> = {}) {
  return { run_id: runId, ...extra };
}

export class BrowserApi {
  static launch(headless: boolean) {
    return Backend.request<BrowserRun>("browser.launch", { headless });
  }

  static stop(runId: string) {
    return Backend.request<BrowserRun>("browser.stop", runPayload(runId));
  }

  static status(runId?: string) {
    return Backend.request<BrowserStatusResult>(
      "browser.status",
      runId ? runPayload(runId) : {},
    );
  }

  static recover(runId: string) {
    return Backend.request<BrowserRun>("browser.recover", runPayload(runId));
  }

  static control(runId: string, action: "pause" | "resume" | "stop") {
    return Backend.request<BrowserRun>("browser.control", runPayload(runId, { action }));
  }

  static installStatus() {
    return Backend.request<BrowserInstallResult>("browser.install.status");
  }

  static installRun() {
    return Backend.request<BrowserInstallResult>("browser.install.run");
  }

  static subscribeInstallProgress(cb: (progress: BrowserInstallProgress) => void) {
    return Backend.subscribeDaemon<BrowserInstallProgress>("browser", (event) => {
      if (event.route === "browser.install.progress") {
        cb(event.payload);
      }
    });
  }

  static unsubscribeInstallProgress(cb: (progress: BrowserInstallProgress) => void) {
    Backend.unsubscribeDaemon(cb as never);
  }

  static subscribe(cb: (event: BrowserEvent) => void) {
    return Backend.subscribeDaemon(CHANNEL, cb);
  }

  static unsubscribe(cb: (event: BrowserEvent) => void) {
    Backend.unsubscribeDaemon(cb as (event: DaemonEvent<unknown>) => void);
  }
}

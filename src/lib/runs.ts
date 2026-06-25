import { Backend, type DaemonEvent } from "@/lib/api";

export type RunStatus =
  | "idle"
  | "running"
  | "paused"
  | "stopping"
  | "completed"
  | "failed"
  | "stopped"
  | "shutdown";

export type RunInfo = {
  id: string;
  platform: string;
  task: string;
  status: RunStatus;
  params: Record<string, unknown>;
  log: string;
  pause_info: Record<string, unknown> | null;
  error: string | null;
  item_count: number;
  first_run_at: string | null;
  last_run_at: string | null;
  re_run_count: number;
  created_at: string;
  updated_at: string;
};

export type RunInput = {
  id: string;
  run_id: string;
  ordinal: number;
  status: string;
  data: Record<string, unknown>;
  cursor: Record<string, unknown> | null;
  created_at: string;
};

export type RunItem = {
  id: string;
  run_id: string;
  input_id: string;
  item_key: string;
  ordinal: number;
  data: Record<string, unknown>;
  created_at: string;
};

export type RunControlAction = "pause" | "resume" | "stop";

export type RunStatusPayload = {
  run_id: string;
  status: RunStatus;
  pause_info?: Record<string, unknown> | null;
  error?: string | null;
};

export type RunItemPayload = RunItem;

export type RunInputStatusPayload = {
  run_id: string;
  input_id: string;
  status: string;
  cursor?: Record<string, unknown> | null;
};

export type RunLogPayload = {
  run_id: string;
  ts?: number;
  level?: string;
  line: string;
};

export type RunProgressPayload = {
  run_id: string;
  [key: string]: unknown;
};

export type RunEventPayload =
  | RunStatusPayload
  | RunItemPayload
  | RunInputStatusPayload
  | RunLogPayload
  | RunProgressPayload;

export type RunEvent = DaemonEvent<RunEventPayload>;

const CHANNEL = "runs";

export const ACTIVE_RUN_STATUSES: RunStatus[] = ["running", "paused", "stopping"];

export function isActiveRun(run: RunInfo): boolean {
  return ACTIVE_RUN_STATUSES.includes(run.status);
}

export function isResumableRun(run: RunInfo): boolean {
  return (
    run.status === "paused" ||
    run.status === "shutdown" ||
    run.status === "stopped" ||
    run.status === "failed"
  );
}

export class RunsApi {
  static list(platform?: string) {
    return Backend.request<RunInfo[]>("runs.list", platform ? { platform } : {});
  }

  static get(runId: string) {
    return Backend.request<RunInfo>("runs.get", { run_id: runId });
  }

  static inputs(runId: string) {
    return Backend.request<RunInput[]>("runs.inputs", { run_id: runId });
  }

  static items(runId: string, inputId?: string) {
    return Backend.request<RunItem[]>(
      "runs.items",
      inputId ? { run_id: runId, input_id: inputId } : { run_id: runId },
    );
  }

  static start(
    platform: string,
    task: string,
    params: Record<string, unknown>,
    inputs: Record<string, unknown>[],
  ) {
    return Backend.request<RunInfo>("runs.start", {
      platform,
      task,
      params,
      inputs,
    });
  }

  static control(runId: string, action: RunControlAction) {
    return Backend.request<RunInfo>("runs.control", {
      run_id: runId,
      action,
    });
  }

  static restart(runId: string) {
    return Backend.request<RunInfo>("runs.restart", { run_id: runId });
  }

  static delete(runId: string) {
    return Backend.request<void>("runs.delete", { run_id: runId });
  }

  static subscribe(cb: (event: RunEvent) => void) {
    return Backend.subscribeDaemon<RunEventPayload>(CHANNEL, cb);
  }

  static unsubscribe(cb: (event: RunEvent) => void) {
    Backend.unsubscribeDaemon(cb as never);
  }
}

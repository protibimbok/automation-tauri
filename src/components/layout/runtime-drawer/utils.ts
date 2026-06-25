import { type BrowserRun } from "@/lib/browser";
import { isActiveRun, type RunInfo } from "@/lib/runs";
import { taskLabel } from "@/lib/tasks";

export const STATUS_TONE: Record<string, string> = {
  running: "bg-primary",
  paused: "bg-amber-500",
  stopping: "bg-amber-500",
  completed: "bg-emerald-500",
  failed: "bg-destructive",
  stopped: "bg-muted-foreground",
  shutdown: "bg-muted-foreground",
  idle: "bg-muted-foreground",
};

export function shortId(runId: string) {
  return runId.slice(0, 8);
}

export function formatTime(ts: number) {
  return new Date(ts * 1000).toLocaleTimeString();
}

function browserUrlFromRun(run: RunInfo): string {
  const profileUrl = run.pause_info?.profile_url;
  if (typeof profileUrl === "string" && profileUrl.trim()) {
    return profileUrl.trim();
  }
  return taskLabel(run.task);
}

export function taskBrowserInstances(runs: RunInfo[]): BrowserRun[] {
  return runs.filter(isActiveRun).map((run) => ({
    ok: true,
    run_id: run.id,
    running: true,
    headless: Boolean(run.params.headless ?? true),
    url: browserUrlFromRun(run),
    paused: run.status === "paused",
    crashed: false,
  }));
}

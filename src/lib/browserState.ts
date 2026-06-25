import type { BrowserEvent, BrowserRun } from "@/lib/browser";

export function isBrowserRun(value: unknown): value is BrowserRun {
  return (
    typeof value === "object" &&
    value !== null &&
    "run_id" in value &&
    typeof (value as BrowserRun).run_id === "string"
  );
}

export function normalizeBrowserInstances(result: unknown): BrowserRun[] {
  if (
    typeof result === "object" &&
    result !== null &&
    "instances" in result &&
    Array.isArray((result as { instances: unknown }).instances)
  ) {
    return (result as { instances: BrowserRun[] }).instances.filter(
      (instance) => instance.running,
    );
  }
  if (isBrowserRun(result)) {
    return result.running ? [result] : [];
  }
  return [];
}

export function upsertBrowserInstance(
  instances: BrowserRun[],
  next: BrowserRun,
): BrowserRun[] {
  if (!next.running) {
    return instances.filter((instance) => instance.run_id !== next.run_id);
  }
  return [
    ...instances.filter((instance) => instance.run_id !== next.run_id),
    next,
  ];
}

export function applyBrowserEvent(
  instances: BrowserRun[],
  event: BrowserEvent,
): BrowserRun[] {
  if (event.route === "browser.closed") {
    return instances.filter(
      (instance) => instance.run_id !== event.payload.run_id,
    );
  }
  if (event.route === "browser.updated") {
    return upsertBrowserInstance(instances, event.payload);
  }
  return instances;
}

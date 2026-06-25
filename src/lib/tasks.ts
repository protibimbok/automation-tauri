import type { LucideIcon } from "lucide-react";
import type { ComponentType, ReactNode } from "react";

import type { RunInfo } from "@/lib/runs";

/**
 * Which lifecycle controls a task type supports. The RuntimeDrawer renders the
 * relevant buttons based on these flags combined with the run's current status.
 */
export interface TaskCapabilities {
  pause: boolean;
  resume: boolean;
  stop: boolean;
  restart: boolean;
}

export const DEFAULT_TASK_CAPABILITIES: TaskCapabilities = {
  pause: true,
  resume: true,
  stop: true,
  restart: true,
};

export interface TaskTypeDefinition {
  /** Matches the backend task key, e.g. "linkedin.posts_scraper". */
  key: string;
  /** Platform slug, e.g. "linkedin". */
  platform: string;
  label: string;
  icon: LucideIcon;
  capabilities: TaskCapabilities;
  /** Task-owned UI for displaying a run's result data. */
  ResultsView?: ComponentType<{ runId: string }>;
  /** Optional short summary rendered in the run's drawer tab. */
  renderSummary?: (run: RunInfo) => ReactNode;
  /** Optional route to a full-page results view for a run. */
  resultsPath?: (runId: string) => string;
}

const taskTypes = new Map<string, TaskTypeDefinition>();

export function registerTaskType(definition: TaskTypeDefinition): void {
  if (taskTypes.has(definition.key)) {
    console.warn(`[tasks] task type "${definition.key}" is already registered`);
    return;
  }
  taskTypes.set(definition.key, definition);
}

export function getTaskType(key: string): TaskTypeDefinition | undefined {
  return taskTypes.get(key);
}

export function getTaskTypes(): TaskTypeDefinition[] {
  return [...taskTypes.values()];
}

export function taskLabel(key: string): string {
  return taskTypes.get(key)?.label ?? key;
}

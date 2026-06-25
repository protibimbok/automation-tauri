import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ExternalLink } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Combobox,
  ComboboxContent,
  ComboboxEmpty,
  ComboboxInput,
  ComboboxItem,
  ComboboxList,
} from "@/components/ui/combobox";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useRunLog, useRuns } from "@/hooks/useRuns";
import { isActiveRun, isResumableRun, type RunInfo } from "@/lib/runs";
import { getTaskType, taskLabel } from "@/lib/tasks";

import { STATUS_TONE, shortId } from "./utils";

function RunControls({
  run,
  pending,
  onControl,
  onRestart,
  onRemove,
  onNavigate,
}: {
  run: RunInfo;
  pending: boolean;
  onControl: (action: "pause" | "resume" | "stop") => void;
  onRestart: () => void;
  onRemove: () => void;
  onNavigate: () => void;
}) {
  const taskType = getTaskType(run.task);
  const caps = taskType?.capabilities ?? {
    pause: false,
    resume: false,
    stop: false,
    restart: false,
  };
  const resultsPath = taskType?.resultsPath?.(run.id);

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="text-sm font-medium">{taskLabel(run.task)}</p>
          <p className="text-xs text-muted-foreground">
            {shortId(run.id)} · {run.item_count} items · {run.re_run_count}{" "}
            re-runs
          </p>
        </div>
        <span className="text-xs capitalize text-muted-foreground">
          {run.status}
        </span>
      </div>

      {run.error && <p className="text-xs text-destructive">{run.error}</p>}

      <div className="flex flex-wrap gap-1.5">
        {caps.pause && run.status === "running" && (
          <Button
            variant="outline"
            size="xs"
            disabled={pending}
            onClick={() => onControl("pause")}
          >
            Pause
          </Button>
        )}
        {caps.resume && run.status === "paused" && (
          <Button
            variant="outline"
            size="xs"
            disabled={pending}
            onClick={() => onControl("resume")}
          >
            Resume
          </Button>
        )}
        {caps.stop &&
          (run.status === "running" ||
            run.status === "paused" ||
            run.status === "stopping") && (
            <Button
              variant="destructive"
              size="xs"
              disabled={pending}
              onClick={() => onControl("stop")}
            >
              Stop
            </Button>
          )}
        {caps.restart && isResumableRun(run) && (
          <Button
            variant="outline"
            size="xs"
            disabled={pending}
            onClick={onRestart}
          >
            Restart
          </Button>
        )}
        {resultsPath && (
          <Button
            variant="ghost"
            size="xs"
            render={<Link to={resultsPath} />}
            onClick={onNavigate}
          >
            <ExternalLink />
            Results
          </Button>
        )}
        <Button variant="ghost" size="xs" disabled={pending} onClick={onRemove}>
          Delete
        </Button>
      </div>
    </div>
  );
}

function RunLogPanel({ runId }: { runId: string }) {
  const lines = useRunLog(runId);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [lines]);

  return (
    <ScrollArea className="min-h-0 flex-1 rounded-md border bg-muted/30 p-2">
      <div className="flex flex-col gap-0.5 pr-3">
        {lines.length === 0 ? (
          <p className="text-xs text-muted-foreground">No log output yet.</p>
        ) : (
          lines.map((line, index) => (
            <div
              key={`${index}-${line.slice(0, 12)}`}
              className="font-mono text-xs leading-relaxed wrap-break-word"
            >
              {line}
            </div>
          ))
        )}
        <div ref={endRef} />
      </div>
    </ScrollArea>
  );
}

type TaskOption = { value: string; label: string; status: RunInfo["status"] };

export function TasksRuntimePanel({
  open,
  onNavigate,
}: {
  open: boolean;
  onNavigate: () => void;
}) {
  const { runs, control, restart, remove, pendingRunId, refresh } = useRuns();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<RunInfo | null>(null);

  const runningRuns = runs.filter(isActiveRun);

  useEffect(() => {
    if (open) void refresh();
  }, [open, refresh]);

  useEffect(() => {
    if (runningRuns.length === 0) {
      setSelectedId(null);
      return;
    }
    setSelectedId((current) =>
      current && runningRuns.some((run) => run.id === current)
        ? current
        : runningRuns[0].id,
    );
  }, [runningRuns]);

  const selectedRun = runningRuns.find((run) => run.id === selectedId) ?? null;

  if (runningRuns.length === 0) {
    return (
      <div className="flex flex-1 items-center justify-center p-6">
        <p className="text-sm text-muted-foreground">
          No running tasks. Start one from a module page.
        </p>
      </div>
    );
  }

  const options: TaskOption[] = runningRuns.map((run) => ({
    value: run.id,
    label: `${taskLabel(run.task)} ${shortId(run.id)}`,
    status: run.status,
  }));
  const selectedOption =
    options.find((option) => option.value === selectedId) ?? null;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="border-b px-4 py-3">
        <Combobox
          items={options}
          value={selectedOption}
          onValueChange={(value) => setSelectedId(value?.value ?? null)}
          itemToStringLabel={(item: TaskOption) => item.label}
        >
          <ComboboxInput placeholder="Select a task…" />
          <ComboboxContent>
            <ComboboxEmpty>No running tasks.</ComboboxEmpty>
            <ComboboxList>
              {(item: TaskOption) => (
                <ComboboxItem key={item.value} value={item}>
                  <span
                    className={`size-1.5 rounded-full ${
                      STATUS_TONE[item.status] ?? "bg-muted-foreground"
                    }`}
                  />
                  {item.label}
                </ComboboxItem>
              )}
            </ComboboxList>
          </ComboboxContent>
        </Combobox>
      </div>

      {selectedRun && (
        <div className="border-b px-4 py-3">
          <RunControls
            run={selectedRun}
            pending={pendingRunId === selectedRun.id}
            onControl={(action) => void control(selectedRun.id, action)}
            onRestart={() => void restart(selectedRun.id)}
            onRemove={() => setDeleteTarget(selectedRun)}
            onNavigate={onNavigate}
          />
        </div>
      )}

      <div className="flex min-h-0 flex-1 flex-col gap-2 px-4 py-3">
        <h3 className="text-sm font-medium">Log</h3>
        {selectedRun ? (
          <RunLogPanel key={selectedRun.id} runId={selectedRun.id} />
        ) : (
          <p className="text-sm text-muted-foreground">
            Select a run to view its log.
          </p>
        )}
      </div>

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        title="Delete run?"
        description={
          deleteTarget
            ? `Permanently delete run ${shortId(deleteTarget.id)} and all scraped results? This cannot be undone.`
            : ""
        }
        confirmLabel="Delete"
        destructive
        pending={deleteTarget !== null && pendingRunId === deleteTarget.id}
        onConfirm={async () => {
          if (!deleteTarget) return;
          const deleted = await remove(deleteTarget.id);
          if (deleted) setDeleteTarget(null);
        }}
      />
    </div>
  );
}

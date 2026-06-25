import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowLeft,
  Pause,
  Play,
  RotateCcw,
  Square,
  Trash2,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { useRunInputs, useRuns } from "@/hooks/useRuns";
import { isResumableRun, type RunInfo } from "@/lib/runs";

import { PostsResultsView } from "./PostsResultsView";
import { RunInputFilter } from "./RunInputFilter";

function RunControls({
  run,
  pending,
  onControl,
  onRestart,
  onDelete,
}: {
  run: RunInfo;
  pending: boolean;
  onControl: (action: "pause" | "resume" | "stop") => void;
  onRestart: () => void;
  onDelete: () => void;
}) {
  const active =
    run.status === "running" ||
    run.status === "paused" ||
    run.status === "stopping";

  return (
    <div className="flex flex-wrap items-center justify-end gap-1.5">
      {run.status === "running" && (
        <Button
          variant="outline"
          size="sm"
          disabled={pending}
          onClick={() => onControl("pause")}
        >
          <Pause />
          Pause
        </Button>
      )}
      {run.status === "paused" && (
        <Button
          variant="outline"
          size="sm"
          disabled={pending}
          onClick={() => onControl("resume")}
        >
          <Play />
          Resume
        </Button>
      )}
      {active && (
        <Button
          variant="destructive"
          size="sm"
          disabled={pending}
          onClick={() => onControl("stop")}
        >
          <Square />
          Stop
        </Button>
      )}
      {isResumableRun(run) && (
        <Button
          variant="outline"
          size="sm"
          disabled={pending}
          onClick={onRestart}
        >
          <RotateCcw />
          Re-run
        </Button>
      )}
      <Button
        variant="ghost"
        size="sm"
        disabled={pending}
        onClick={onDelete}
      >
        <Trash2 />
        Delete
      </Button>
    </div>
  );
}

export function PostsResultsPage() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const { runs, control, restart, remove, pendingRunId } = useRuns("linkedin");
  const [deleteOpen, setDeleteOpen] = useState(false);
  const [selectedInputId, setSelectedInputId] = useState<string | null>(null);
  const {
    inputs,
    error: inputsError,
    refresh: refreshInputs,
  } = useRunInputs(runId ?? "");

  if (!runId) {
    return (
      <div className="p-6 text-sm text-muted-foreground">No run selected.</div>
    );
  }

  const run = runs.find((item) => item.id === runId) ?? null;

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 p-6">
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <Button
            variant="ghost"
            size="icon-sm"
            render={<Link to="/platforms/linkedin/posts" />}
          >
            <ArrowLeft />
          </Button>
          <div className="min-w-0">
            <h1 className="text-xl font-semibold tracking-tight">
              Scrape results
            </h1>
            <p className="truncate text-sm text-muted-foreground">
              Run {runId.slice(0, 8)}
              {run ? ` · ${run.status} · ${run.item_count} posts` : ""}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center justify-end gap-2">
          <RunInputFilter
            inputs={inputs}
            selectedInputId={selectedInputId}
            onChange={setSelectedInputId}
            className="w-56 sm:w-64"
          />
          {run && (
            <RunControls
              run={run}
              pending={pendingRunId === run.id}
              onControl={(action) => void control(run.id, action)}
              onRestart={() => void restart(run.id)}
              onDelete={() => setDeleteOpen(true)}
            />
          )}
        </div>
      </div>

      {inputsError && (
        <p className="text-sm text-destructive">{inputsError}</p>
      )}

      <PostsResultsView
        runId={runId}
        selectedInputId={selectedInputId}
        onRefreshInputs={refreshInputs}
      />

      <ConfirmDialog
        open={deleteOpen}
        onOpenChange={setDeleteOpen}
        title="Delete run?"
        description={`Permanently delete run ${runId.slice(0, 8)} and all scraped results? This cannot be undone.`}
        confirmLabel="Delete"
        destructive
        pending={pendingRunId === runId}
        onConfirm={async () => {
          const deleted = await remove(runId);
          if (deleted) {
            setDeleteOpen(false);
            navigate("/platforms/linkedin/posts");
          }
        }}
      />
    </div>
  );
}

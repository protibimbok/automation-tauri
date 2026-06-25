import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Plus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { useRuns } from "@/hooks/useRuns";
import { isResumableRun, type RunInfo } from "@/lib/runs";
import { SessionPicker, usePlatformSessions } from "@/modules/sessions";

import { LinkedinApi } from "../api";
import type { PostScraperParams } from "../types";

const STATUS_TONE: Record<string, string> = {
  running: "text-primary",
  paused: "text-amber-500",
  stopping: "text-amber-500",
  completed: "text-emerald-500",
  failed: "text-destructive",
  stopped: "text-muted-foreground",
  shutdown: "text-muted-foreground",
};

function RunRow({
  run,
  pending,
  onControl,
  onRestart,
  onRemove,
}: {
  run: RunInfo;
  pending: boolean;
  onControl: (action: "pause" | "resume" | "stop") => void;
  onRestart: () => void;
  onRemove: () => void;
}) {
  const tone = STATUS_TONE[run.status] ?? "text-muted-foreground";
  return (
    <div className="rounded-lg border px-3 py-2 text-sm">
      <div className="flex items-center justify-between gap-2">
        <Link
          to={`/platforms/linkedin/posts/runs/${run.id}`}
          className="font-medium underline-offset-4 hover:underline"
        >
          {run.id.slice(0, 8)}
        </Link>
        <span className={`text-xs capitalize ${tone}`}>{run.status}</span>
      </div>
      <p className="mt-1 text-xs text-muted-foreground">
        {run.item_count} posts · {run.re_run_count} re-runs ·{" "}
        {new Date(run.updated_at).toLocaleString()}
      </p>
      {run.error && (
        <p className="mt-1 text-xs text-destructive">{run.error}</p>
      )}
      <div className="mt-2 flex flex-wrap gap-1.5">
        {run.status === "running" && (
          <Button
            variant="outline"
            size="xs"
            disabled={pending}
            onClick={() => onControl("pause")}
          >
            Pause
          </Button>
        )}
        {run.status === "paused" && (
          <Button
            variant="outline"
            size="xs"
            disabled={pending}
            onClick={() => onControl("resume")}
          >
            Resume
          </Button>
        )}
        {(run.status === "running" ||
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
        {isResumableRun(run) && (
          <Button
            variant="outline"
            size="xs"
            disabled={pending}
            onClick={onRestart}
          >
            Restart
          </Button>
        )}
        <Button
          variant="ghost"
          size="xs"
          disabled={pending}
          onClick={onRemove}
        >
          Delete
        </Button>
      </div>
    </div>
  );
}

export function PostScraperPage() {
  const navigate = useNavigate();
  const { sessions } = usePlatformSessions("linkedin");
  const { runs, control, restart, remove, pendingRunId, error: runsError } =
    useRuns("linkedin");

  const [sessionId, setSessionId] = useState("");
  const [profileMode, setProfileMode] = useState<"list" | "bulk">("list");
  const [profiles, setProfiles] = useState<string[]>([""]);
  const [bulkProfiles, setBulkProfiles] = useState("");
  const [postCount, setPostCount] = useState("");
  const [startFrom, setStartFrom] = useState("1");
  const [matcher, setMatcher] = useState("");
  const [headless, setHeadless] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<RunInfo | null>(null);

  const profileUrls = () => {
    if (profileMode === "bulk") {
      return bulkProfiles
        .split("\n")
        .map((profile) => profile.trim())
        .filter(Boolean);
    }
    return profiles.map((profile) => profile.trim()).filter(Boolean);
  };

  const switchProfileMode = (mode: "list" | "bulk") => {
    if (mode === profileMode) return;
    if (mode === "bulk") {
      setBulkProfiles(profiles.map((profile) => profile.trim()).filter(Boolean).join("\n"));
    } else {
      const lines = bulkProfiles
        .split("\n")
        .map((profile) => profile.trim())
        .filter(Boolean);
      setProfiles(lines.length > 0 ? lines : [""]);
    }
    setProfileMode(mode);
  };

  const updateProfile = (index: number, value: string) => {
    setProfiles((prev) => prev.map((p, i) => (i === index ? value : p)));
  };
  const addProfile = () => setProfiles((prev) => [...prev, ""]);
  const removeProfile = (index: number) =>
    setProfiles((prev) =>
      prev.length === 1 ? prev : prev.filter((_, i) => i !== index),
    );

  const start = async () => {
    setError(null);
    const urls = profileUrls();
    if (!sessionId) {
      setError("Select a LinkedIn session to scrape with.");
      return;
    }
    if (urls.length === 0) {
      setError("Add at least one profile URL.");
      return;
    }

    const params: PostScraperParams = {
      session_id: sessionId,
      headless,
      post_count: postCount ? Number(postCount) : null,
      start_from: startFrom ? Number(startFrom) : 1,
      post_matcher: matcher.trim() || null,
    };

    setSubmitting(true);
    try {
      const run = await LinkedinApi.startPostScrape(params, urls);
      navigate(`/platforms/linkedin/posts/runs/${run.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-6 p-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          LinkedIn Post Scraper
        </h1>
        <p className="text-sm text-muted-foreground">
          Scrape posts from one or more LinkedIn profiles using a logged-in
          session. Runs can be paused, resumed, and restarted from the runtime
          panel.
        </p>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-6 lg:grid-cols-2">
        <section className="flex flex-col gap-4 rounded-lg border bg-card p-4">
          <h2 className="text-sm font-medium">New run</h2>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              Session
            </label>
            <SessionPicker
              platform="linkedin"
              sessions={sessions}
              value={sessionId}
              onChange={setSessionId}
              emptyMessage="No LinkedIn sessions yet — create one under"
            />
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              Profile inputs
            </label>
            <Tabs
              value={profileMode}
              onValueChange={(value) => switchProfileMode(value as "list" | "bulk")}
            >
              <TabsList>
                <TabsTrigger value="list">List</TabsTrigger>
                <TabsTrigger value="bulk">Bulk text</TabsTrigger>
              </TabsList>
              <TabsContent value="list" className="space-y-2">
                {profiles.map((profile, index) => (
                  <div key={index} className="flex items-center gap-2">
                    <Input
                      value={profile}
                      placeholder="https://www.linkedin.com/in/username/ or username"
                      onChange={(e) => updateProfile(index, e.target.value)}
                    />
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      disabled={profiles.length === 1}
                      onClick={() => removeProfile(index)}
                    >
                      <Trash2 />
                    </Button>
                  </div>
                ))}
                <Button variant="outline" size="sm" onClick={addProfile}>
                  <Plus />
                  Add profile
                </Button>
              </TabsContent>
              <TabsContent value="bulk">
                <textarea
                  className="min-h-32 w-full rounded-lg border border-input bg-transparent px-2.5 py-1.5 font-mono text-xs outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                  value={bulkProfiles}
                  placeholder={
                    "https://www.linkedin.com/in/username/\nusername\nhttps://www.linkedin.com/in/another/"
                  }
                  onChange={(e) => setBulkProfiles(e.target.value)}
                />
                <p className="mt-1 text-xs text-muted-foreground">
                  One profile URL or username per line.
                </p>
              </TabsContent>
            </Tabs>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                Posts per profile (blank = all)
              </label>
              <Input
                type="number"
                min={1}
                value={postCount}
                placeholder="all"
                onChange={(e) => setPostCount(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-muted-foreground">
                Start from #
              </label>
              <Input
                type="number"
                min={1}
                value={startFrom}
                onChange={(e) => setStartFrom(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-xs font-medium text-muted-foreground">
              Post matcher (optional JS body, return boolean)
            </label>
            <textarea
              className="min-h-16 w-full rounded-lg border border-input bg-transparent px-2.5 py-1.5 font-mono text-xs outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
              value={matcher}
              placeholder="return post.text.includes('hiring');"
              onChange={(e) => setMatcher(e.target.value)}
            />
          </div>

          <label className="flex cursor-pointer items-center gap-2 text-sm">
            <input
              type="checkbox"
              className="size-4 rounded border"
              checked={headless}
              onChange={(e) => setHeadless(e.target.checked)}
            />
            Run headless
          </label>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <Button onClick={() => void start()} disabled={submitting}>
            {submitting ? "Starting…" : "Start scrape"}
          </Button>
        </section>

        <section className="flex min-h-0 flex-col gap-3 rounded-lg border bg-card p-4">
          <h2 className="text-sm font-medium">Runs</h2>
          {runsError && <p className="text-sm text-destructive">{runsError}</p>}
          <Separator />
          <ScrollArea className="min-h-0 flex-1">
            {runs.length === 0 ? (
              <p className="text-sm text-muted-foreground">No runs yet.</p>
            ) : (
              <div className="flex flex-col gap-2 pr-3">
                {runs.map((run) => (
                  <RunRow
                    key={run.id}
                    run={run}
                    pending={pendingRunId === run.id}
                    onControl={(action) => void control(run.id, action)}
                    onRestart={() => void restart(run.id)}
                    onRemove={() => setDeleteTarget(run)}
                  />
                ))}
              </div>
            )}
          </ScrollArea>
        </section>
      </div>

      <ConfirmDialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
        title="Delete run?"
        description={
          deleteTarget
            ? `Permanently delete run ${deleteTarget.id.slice(0, 8)} and all scraped results? This cannot be undone.`
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

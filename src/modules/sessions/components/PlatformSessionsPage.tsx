import { useState } from "react";
import { useParams } from "react-router-dom";
import { Cookie, Play, RefreshCw, ShieldCheck, Square, Trash2, Users } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Spinner } from "@/components/ui/spinner";
import { SessionCookiesDialog } from "@/modules/sessions/components/SessionCookiesDialog";
import { useSessions } from "@/modules/sessions/hooks";
import { findPlatform, type PlatformSlug } from "@/modules/sessions/platforms";
import { DEFAULT_CHROME_SESSION_ID, isSessionBrowserOpen, sessionBrowserStatus, usesSystemProfile, type SessionInfo } from "@/modules/sessions/types";

function statusClass(status: string) {
  switch (status) {
    case "running":
      return "bg-primary/15 text-primary";
    case "error":
      return "bg-destructive/15 text-destructive";
    default:
      return "bg-muted text-muted-foreground";
  }
}

export function PlatformSessionsPage() {
  const { platform: platformSlug } = useParams<{ platform: PlatformSlug }>();
  const platform = platformSlug ? findPlatform(platformSlug) : undefined;
  const {
    items: sessions,
    liveRuns,
    pending,
    pendingSessionId,
    error,
    lastCheck,
    createSession,
    addDefaultChrome,
    launchSession,
    stopSession,
    checkSession,
    syncSession,
    deleteSession,
    clearError,
  } = useSessions(platformSlug);

  const [name, setName] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [cookiesSession, setCookiesSession] = useState<SessionInfo | null>(null);

  const busy = pending !== null;
  const selected =
    sessions.find((session) => session.id === selectedId) ?? null;
  const hasDefaultChrome = sessions.some(
    (session) => session.id === DEFAULT_CHROME_SESSION_ID,
  );

  if (!platformSlug || !platform) {
    return (
      <div className="flex flex-1 items-center justify-center p-6 text-sm text-muted-foreground">
        Unknown platform.
      </div>
    );
  }

  const handleCreateAndLaunch = async () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    const created = await createSession(trimmed, true);
    if (created) {
      setName("");
      setSelectedId(created.id);
    }
  };

  const isPending = (sessionId: string) => busy && pendingSessionId === sessionId;

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 p-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">
          {platform.name} Sessions
        </h1>
        <p className="text-sm text-muted-foreground">
          Each session keeps its own browser cookies. Launch to sign in; cookies
          are saved when the window closes.
        </p>
      </div>

      <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <section className="flex min-h-80 flex-col rounded-lg border bg-card">
          <div className="flex items-center justify-between border-b px-4 py-3">
            <div className="flex items-center gap-2 text-sm font-medium">
              <Users className="size-4" />
              Sessions ({sessions.length})
            </div>
          </div>

          <ScrollArea className="flex-1">
            <div className="divide-y">
              {sessions.length === 0 ? (
                <p className="p-4 text-sm text-muted-foreground">
                  No sessions yet. Create one using the form on the right.
                </p>
              ) : (
                sessions.map((session) => {
                  const check = lastCheck[session.id];
                  const active = selectedId === session.id;
                  const browserOpen = isSessionBrowserOpen(session, liveRuns);
                  const browserStatus = sessionBrowserStatus(session, liveRuns);
                  return (
                    <div
                      key={session.id}
                      className={`flex flex-col gap-3 p-4 transition-colors ${
                        active ? "bg-accent/50" : "hover:bg-muted/40"
                      }`}
                    >
                      <button
                        type="button"
                        className="flex w-full items-start justify-between gap-2 text-left"
                        onClick={() => setSelectedId(session.id)}
                      >
                        <div className="min-w-0">
                          <p className="truncate font-medium">{session.name}</p>
                          <p className="truncate text-xs text-muted-foreground">
                            {usesSystemProfile(session)
                              ? session.has_storage
                                ? "Synced from system Chrome"
                                : "Not synced from system Chrome yet"
                              : session.has_storage
                                ? "Cookies saved"
                                : "No cookies yet"}
                            {browserOpen
                              ? " · browser open"
                              : ""}
                            {check
                              ? ` · ${check.logged_in ? "logged in" : "not logged in"}`
                              : ""}
                          </p>
                        </div>
                        <span
                          className={`shrink-0 rounded px-2 py-0.5 text-xs font-medium capitalize ${statusClass(browserStatus)}`}
                        >
                          {browserStatus}
                        </span>
                      </button>

                      <div className="flex flex-wrap gap-2">
                        {browserOpen ? (
                          <Button
                            type="button"
                            size="sm"
                            variant="secondary"
                            disabled={busy || isPending(session.id)}
                            onClick={() => void stopSession(session.id)}
                          >
                            {isPending(session.id) && pending === "stop" ? (
                              <Spinner className="size-3.5" />
                            ) : (
                              <Square className="size-3.5" />
                            )}
                            Close browser
                          </Button>
                        ) : (
                          <Button
                            type="button"
                            size="sm"
                            variant="secondary"
                            disabled={busy || isPending(session.id)}
                            onClick={() => void launchSession(session.id, false)}
                          >
                            {isPending(session.id) && pending === "launch" ? (
                              <Spinner className="size-3.5" />
                            ) : (
                              <Play className="size-3.5" />
                            )}
                            Launch
                          </Button>
                        )}
                        {usesSystemProfile(session) ? (
                          <Button
                            type="button"
                            size="sm"
                            variant="outline"
                            disabled={
                              busy ||
                              browserOpen ||
                              isPending(session.id)
                            }
                            onClick={() => void syncSession(session.id)}
                          >
                            {isPending(session.id) && pending === "sync" ? (
                              <Spinner className="size-3.5" />
                            ) : (
                              <RefreshCw className="size-3.5" />
                            )}
                            Sync
                          </Button>
                        ) : null}
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={
                            busy ||
                            browserOpen ||
                            isPending(session.id)
                          }
                          onClick={() => void checkSession(session.id)}
                        >
                          {isPending(session.id) && pending === "check" ? (
                            <Spinner className="size-3.5" />
                          ) : (
                            <ShieldCheck className="size-3.5" />
                          )}
                          Check
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          disabled={!session.has_storage}
                          onClick={() => setCookiesSession(session)}
                        >
                          <Cookie className="size-3.5" />
                          Cookies
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="destructive"
                          disabled={busy || browserOpen || isPending(session.id)}
                          onClick={async () => {
                            const ok = await deleteSession(session.id);
                            if (ok && selectedId === session.id) {
                              setSelectedId(null);
                            }
                          }}
                        >
                          {isPending(session.id) && pending === "delete" ? (
                            <Spinner className="size-3.5" />
                          ) : (
                            <Trash2 className="size-3.5" />
                          )}
                          Delete
                        </Button>
                      </div>
                    </div>
                  );
                })
              )}
            </div>
          </ScrollArea>
        </section>

        <section className="flex flex-col rounded-lg border bg-card p-6">
          <h2 className="text-lg font-medium">New session</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Opens a fresh browser window. Log in on the platform; cookies are
            stored for this session when you close the browser.
          </p>

          <Separator className="my-4" />

          <div className="flex flex-col gap-4">
            <div className="space-y-2">
              <label htmlFor="session-name" className="text-sm font-medium">
                Session name
              </label>
              <Input
                id="session-name"
                placeholder={`e.g. ${platform.name} account 1`}
                value={name}
                disabled={busy}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") void handleCreateAndLaunch();
                }}
              />
            </div>

            <Button
              type="button"
              disabled={busy || !name.trim()}
              onClick={() => void handleCreateAndLaunch()}
            >
              {pending === "create" ? (
                <>
                  <Spinner className="size-4" />
                  Opening browser…
                </>
              ) : (
                "Open fresh browser"
              )}
            </Button>

            <Separator />

            <div className="space-y-2">
              <h3 className="text-sm font-medium">Default Chrome</h3>
              <p className="text-sm text-muted-foreground">
                Copies cookies from your installed Chrome into a debuggable
                profile. Close Chrome before adding or syncing.
              </p>
              <Button
                type="button"
                variant="outline"
                disabled={busy || hasDefaultChrome}
                onClick={() => void addDefaultChrome()}
              >
                {pending === "create_default" ? (
                  <>
                    <Spinner className="size-4" />
                    Adding Default Chrome…
                  </>
                ) : hasDefaultChrome ? (
                  "Default Chrome added"
                ) : (
                  "Add Default Chrome"
                )}
              </Button>
            </div>
          </div>

          {selected && (
            <>
              <Separator className="my-6" />
              <div className="space-y-1 text-sm">
                <p className="font-medium">Selected: {selected.name}</p>
                <p className="text-muted-foreground">
                  Created {new Date(selected.created_at).toLocaleString()}
                </p>
                {selected.last_checked_at && (
                  <p className="text-muted-foreground">
                    Last checked{" "}
                    {new Date(selected.last_checked_at).toLocaleString()}
                  </p>
                )}
              </div>
            </>
          )}
        </section>
      </div>

      {error && (
        <div className="flex items-center justify-between rounded-md border border-destructive/40 bg-destructive/10 px-4 py-2 text-sm text-destructive">
          <span>{error}</span>
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={clearError}
          >
            Dismiss
          </Button>
        </div>
      )}

      <SessionCookiesDialog
        session={cookiesSession}
        open={cookiesSession !== null}
        onOpenChange={(open) => {
          if (!open) setCookiesSession(null);
        }}
      />
    </div>
  );
}

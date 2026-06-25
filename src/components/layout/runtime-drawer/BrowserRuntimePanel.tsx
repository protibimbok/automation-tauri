import { useCallback, useEffect, useRef, useState } from "react";

import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { type BrowserRun } from "@/lib/browser";
import { LogApi, type LogEvent, type LogLine } from "@/lib/log";

import { formatTime, shortId } from "./utils";

function InstanceRow({
  instance,
  source,
}: {
  instance: BrowserRun;
  source?: "task" | "registry";
}) {
  return (
    <li className="rounded-md border px-3 py-2 text-sm">
      <div className="flex items-center justify-between gap-2">
        <span className="font-medium">
          {source === "task" ? instance.url : shortId(instance.run_id)}
        </span>
        <span className="text-xs text-muted-foreground">
          {instance.headless ? "headless" : "visible"}
          {source === "task" ? " · task" : ""}
        </span>
      </div>
      <p className="mt-1 truncate text-xs text-muted-foreground">
        {source === "task"
          ? shortId(instance.run_id)
          : instance.url || "about:blank"}
      </p>
      <div className="mt-1 flex gap-2 text-xs text-muted-foreground">
        {instance.paused && <span>paused</span>}
        {instance.crashed && <span className="text-destructive">crashed</span>}
      </div>
    </li>
  );
}

function LogRow({ line }: { line: LogLine }) {
  return (
    <div className="font-mono text-xs leading-relaxed">
      <span className="text-muted-foreground">{formatTime(line.ts)}</span>{" "}
      <span className="text-muted-foreground">[{line.source}]</span>{" "}
      <span>{line.message}</span>
    </div>
  );
}

export function BrowserRuntimePanel({
  open,
  instances,
  registryInstances,
}: {
  open: boolean;
  instances: BrowserRun[];
  registryInstances: BrowserRun[];
}) {
  const [logs, setLogs] = useState<LogLine[]>([]);
  const logEndRef = useRef<HTMLDivElement>(null);

  const syncLogs = useCallback(async () => {
    try {
      const result = await LogApi.lines();
      if (result.ok) {
        setLogs(result.lines);
      }
    } catch {
      // ignore transient errors
    }
  }, []);

  useEffect(() => {
    if (!open) return;
    void syncLogs();
  }, [open, syncLogs]);

  const instanceSource = new Map<string, "task" | "registry">();
  for (const instance of registryInstances) {
    if (instance.running) {
      instanceSource.set(instance.run_id, "registry");
    }
  }
  for (const instance of instances) {
    if (!instanceSource.has(instance.run_id)) {
      instanceSource.set(instance.run_id, "task");
    }
  }

  useEffect(() => {
    const onLog = (event: LogEvent) => {
      if (event.route !== "log.line" || !open) return;
      setLogs((prev) => [...prev.slice(-499), event.payload]);
    };

    void LogApi.subscribe(onLog);
    return () => LogApi.unsubscribe(onLog);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    logEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs, open]);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex min-h-0 flex-3 flex-col gap-2 px-4 py-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-medium">Browser instances</h3>
          <span className="text-xs text-muted-foreground">
            {instances.length} running
          </span>
        </div>
        <ScrollArea className="min-h-0 flex-1">
          {instances.length === 0 ? (
            <p className="text-sm text-muted-foreground">No browsers running.</p>
          ) : (
            <ul className="flex flex-col gap-2 pr-3">
              {instances.map((instance) => (
                <InstanceRow
                  key={instance.run_id}
                  instance={instance}
                  source={instanceSource.get(instance.run_id)}
                />
              ))}
            </ul>
          )}
        </ScrollArea>
      </div>

      <Separator />

      <div className="flex min-h-0 flex-2 flex-col gap-2 px-4 py-3">
        <h3 className="text-sm font-medium">Logs</h3>
        <ScrollArea className="min-h-0 flex-1 rounded-md border bg-muted/30 p-2">
          <div className="flex flex-col gap-1 pr-3">
            {logs.length === 0 ? (
              <p className="text-xs text-muted-foreground">No log output yet.</p>
            ) : (
              logs.map((line, index) => (
                <LogRow key={`${line.ts}-${index}`} line={line} />
              ))
            )}
            <div ref={logEndRef} />
          </div>
        </ScrollArea>
      </div>
    </div>
  );
}

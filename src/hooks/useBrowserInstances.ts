import { useCallback, useEffect, useMemo, useState } from "react";

import { BrowserApi, type BrowserEvent, type BrowserRun } from "@/lib/browser";
import {
  applyBrowserEvent,
  normalizeBrowserInstances,
} from "@/lib/browserState";

export function mergeBrowserInstances(
  registry: BrowserRun[],
  tasks: BrowserRun[],
): BrowserRun[] {
  const byId = new Map<string, BrowserRun>();
  for (const instance of registry) {
    if (instance.running) {
      byId.set(instance.run_id, instance);
    }
  }
  for (const instance of tasks) {
    if (!byId.has(instance.run_id)) {
      byId.set(instance.run_id, instance);
    }
  }
  return [...byId.values()];
}

/** Registry browsers merged with active task runs; stays live while drawer is closed. */
export function useBrowserInstances(taskInstances: BrowserRun[]) {
  const [registryInstances, setRegistryInstances] = useState<BrowserRun[]>([]);

  const syncInstances = useCallback(async () => {
    try {
      const result = await BrowserApi.status();
      setRegistryInstances(normalizeBrowserInstances(result));
    } catch {
      // ignore transient errors
    }
  }, []);

  useEffect(() => {
    void syncInstances();
  }, [syncInstances]);

  useEffect(() => {
    const onBrowser = (event: BrowserEvent) => {
      setRegistryInstances((prev) => applyBrowserEvent(prev, event));
    };

    void BrowserApi.subscribe(onBrowser);
    return () => BrowserApi.unsubscribe(onBrowser);
  }, []);

  const instances = useMemo(
    () => mergeBrowserInstances(registryInstances, taskInstances),
    [registryInstances, taskInstances],
  );

  return { instances, registryInstances };
}

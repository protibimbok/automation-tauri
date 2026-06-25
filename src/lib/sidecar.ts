import { Backend, type DaemonEvent } from "@/lib/api";
import { BrowserApi } from "@/lib/browser";

const CHANNEL = "sidecar_ready";
const POLL_MS = 300;
const DEFAULT_TIMEOUT_MS = 30_000;

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

export async function waitForSidecar(timeoutMs = DEFAULT_TIMEOUT_MS): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  let ready = false;

  const onReady = (event: DaemonEvent<unknown>) => {
    if (event.route === "sidecar_ready") {
      ready = true;
    }
  };

  await Backend.subscribeDaemon(CHANNEL, onReady);

  try {
    while (!ready && Date.now() < deadline) {
      try {
        const result = await BrowserApi.installStatus();
        if (result.ok) {
          ready = true;
          break;
        }
      } catch {
        // sidecar not reachable yet
      }
      await sleep(POLL_MS);
    }

    if (!ready) {
      throw new Error("Sidecar did not start in time");
    }
  } finally {
    Backend.unsubscribeDaemon(onReady);
  }
}

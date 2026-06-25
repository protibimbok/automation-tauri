import { invoke } from "@tauri-apps/api/core";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";

export type DaemonEvent<T> = {
  route: string;
  payload: T;
};

type DaemonCallback = (event: DaemonEvent<unknown>) => void;

const DAEMONS = new Map<DaemonCallback, UnlistenFn>();

export class Backend {
  static request<T>(route: string, payload: Record<string, unknown> = {}) {
    return invoke<T>("handle_frontend_request", { req: { route, payload } });
  }

  static async subscribeDaemon<T>(channel: string, cb: (event: DaemonEvent<T>) => void) {
    const unlisten = await listen<DaemonEvent<T>>(`daemon://${channel}`, (e) =>
      cb(e.payload),
    );
    DAEMONS.set(cb as DaemonCallback, unlisten);
  }

  static unsubscribeDaemon(cb: DaemonCallback) {
    const unlisten = DAEMONS.get(cb);
    if (unlisten) {
      unlisten();
      DAEMONS.delete(cb);
    }
  }
}

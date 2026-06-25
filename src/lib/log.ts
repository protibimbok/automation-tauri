import { Backend, type DaemonEvent } from "@/lib/api";

export type LogLine = {
  ts: number;
  level: string;
  source: string;
  message: string;
};

export type LogEvent = DaemonEvent<LogLine>;

export type LogLinesResult = {
  ok: boolean;
  lines: LogLine[];
};

const CHANNEL = "log";

export class LogApi {
  static lines() {
    return Backend.request<LogLinesResult>("log.lines");
  }

  static subscribe(cb: (event: LogEvent) => void) {
    return Backend.subscribeDaemon(CHANNEL, cb);
  }

  static unsubscribe(cb: (event: LogEvent) => void) {
    Backend.unsubscribeDaemon(cb as (event: DaemonEvent<unknown>) => void);
  }
}

import { Link } from "react-router-dom";

import type { PlatformSlug } from "@/modules/sessions/platforms";
import { sessionsPath } from "@/modules/sessions/platforms";
import type { SessionInfo } from "@/modules/sessions/types";

type SessionPickerBaseProps = {
  sessions: SessionInfo[];
  platform?: PlatformSlug;
  disabled?: boolean;
  emptyMessage?: string;
};

type SingleSessionPickerProps = SessionPickerBaseProps & {
  multiple?: false;
  value: string;
  onChange: (value: string) => void;
};

type MultiSessionPickerProps = SessionPickerBaseProps & {
  multiple: true;
  value: Set<string>;
  onChange: (value: Set<string>) => void;
};

export type SessionPickerProps = SingleSessionPickerProps | MultiSessionPickerProps;

function sessionLabel(session: SessionInfo) {
  return session.has_storage ? session.name : `${session.name} (not logged in)`;
}

function EmptySessions({
  platform,
  emptyMessage,
}: {
  platform?: PlatformSlug;
  emptyMessage: string;
}) {
  if (!platform) {
    return <p className="text-xs text-muted-foreground">{emptyMessage}</p>;
  }

  return (
    <p className="text-xs text-muted-foreground">
      {emptyMessage}{" "}
      <Link
        to={sessionsPath(platform)}
        className="text-primary underline-offset-4 hover:underline"
      >
        Sessions
      </Link>
      .
    </p>
  );
}

export function SessionPicker(props: SessionPickerProps) {
  const {
    sessions,
    platform,
    disabled = false,
    emptyMessage = "No sessions available — create one under Sessions.",
  } = props;

  if (sessions.length === 0) {
    return <EmptySessions platform={platform} emptyMessage={emptyMessage} />;
  }

  if (props.multiple) {
    const { value, onChange } = props;

    const toggle = (sessionId: string) => {
      const next = new Set(value);
      if (next.has(sessionId)) {
        next.delete(sessionId);
      } else {
        next.add(sessionId);
      }
      onChange(next);
    };

    return (
      <div className="space-y-2">
        {sessions.map((session) => (
          <label
            key={session.id}
            className="flex cursor-pointer items-center gap-2 text-sm"
          >
            <input
              type="checkbox"
              className="size-4 rounded border"
              checked={value.has(session.id)}
              disabled={disabled || session.active_run_count > 0}
              onChange={() => toggle(session.id)}
            />
            <span className="min-w-0 flex-1 truncate">
              {sessionLabel(session)}
            </span>
            <span className="text-xs capitalize text-muted-foreground">
              {session.status}
            </span>
          </label>
        ))}
      </div>
    );
  }

  const { value, onChange } = props;

  return (
    <div className="space-y-2">
      {sessions.map((session) => (
        <label
          key={session.id}
          className="flex cursor-pointer items-center gap-2 text-sm"
        >
          <input
            type="radio"
            name="session-picker"
            className="size-4 border"
            checked={value === session.id}
            disabled={disabled || session.active_run_count > 0}
            onChange={() => onChange(session.id)}
          />
          <span className="min-w-0 flex-1 truncate">
            {sessionLabel(session)}
          </span>
          <span className="text-xs capitalize text-muted-foreground">
            {session.status}
          </span>
        </label>
      ))}
    </div>
  );
}

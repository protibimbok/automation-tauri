import { useEffect, useState } from "react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import { SessionsApi } from "@/modules/sessions/api";
import type { SessionInfo, StoredCookie } from "@/modules/sessions/types";

type SessionCookiesDialogProps = {
  session: SessionInfo | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

function formatExpires(expires: number | null) {
  if (expires == null || expires <= 0) return "session";
  return new Date(expires * 1000).toLocaleString();
}

export function SessionCookiesDialog({
  session,
  open,
  onOpenChange,
}: SessionCookiesDialogProps) {
  const [cookies, setCookies] = useState<StoredCookie[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open || !session) return;

    let cancelled = false;
    setLoading(true);
    setError(null);

    SessionsApi.cookies(session.id)
      .then((rows) => {
        if (!cancelled) setCookies(rows);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
          setCookies([]);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [open, session]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[85vh] w-[calc(100%-2rem)] flex-col overflow-hidden">
        <DialogHeader className="shrink-0">
          <DialogTitle>
            Cookies{session ? ` · ${session.name}` : ""}
          </DialogTitle>
          <DialogDescription>
            Stored cookies from the last saved browser session.
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
            <Spinner className="size-4" />
            Loading cookies…
          </div>
        ) : error ? (
          <p className="text-sm text-destructive">{error}</p>
        ) : cookies.length === 0 ? (
          <p className="py-8 text-center text-sm text-muted-foreground">
            No cookies saved for this session yet.
          </p>
        ) : (
          <div className="min-h-0 min-w-0 flex-1 overflow-auto rounded-md border">
            <table className="w-full table-fixed text-left text-sm">
              <colgroup>
                <col className="w-[20%]" />
                <col className="w-[24%]" />
                <col className="w-[22%]" />
                <col className="w-[34%]" />
              </colgroup>
              <thead className="sticky top-0 z-10 bg-muted/95 backdrop-blur-sm">
                <tr className="border-b">
                  <th className="px-3 py-2 font-medium">Name</th>
                  <th className="px-3 py-2 font-medium">Domain</th>
                  <th className="px-3 py-2 font-medium">Expires</th>
                  <th className="px-3 py-2 font-medium">Value</th>
                </tr>
              </thead>
              <tbody>
                {cookies.map((cookie) => (
                  <tr
                    key={`${cookie.domain}:${cookie.name}`}
                    className="border-b align-top"
                  >
                    <td className="max-w-0 truncate px-3 py-2 font-mono text-xs">
                      <span className="block truncate" title={cookie.name}>
                        {cookie.name}
                      </span>
                    </td>
                    <td className="max-w-0 truncate px-3 py-2 text-xs text-muted-foreground">
                      <span className="block truncate" title={cookie.domain}>
                        {cookie.domain}
                      </span>
                    </td>
                    <td className="max-w-0 truncate px-3 py-2 text-xs text-muted-foreground">
                      <span
                        className="block truncate"
                        title={formatExpires(cookie.expires)}
                      >
                        {formatExpires(cookie.expires)}
                      </span>
                    </td>
                    <td className="max-w-0 truncate px-3 py-2 font-mono text-xs">
                      <span className="block truncate" title={cookie.value}>
                        {cookie.value}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}

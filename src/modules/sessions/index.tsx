import { Users } from "lucide-react";

import { registerModule } from "@/lib/modular";
import { PlatformSessionsPage } from "@/modules/sessions/components/PlatformSessionsPage";
import { sessionsPath, type PlatformSlug } from "@/modules/sessions/platforms";

registerModule({
  id: "sessions",
  order: -1,
  menuFilter: (menu) =>
    menu.map((group) => {
      if (!group.type?.includes("sessionable") || !group.platform) {
        return group;
      }

      return {
        ...group,
        items: [
          ...group.items,
          {
            label: "Sessions",
            icon: Users,
            path: sessionsPath(group.platform as PlatformSlug),
          },
        ],
      };
    }),
  routes: [
    {
      path: "platforms/:platform/sessions",
      element: <PlatformSessionsPage />,
    },
  ],
});

export { SessionsApi } from "./api";
export { SessionCookiesDialog } from "./components/SessionCookiesDialog";
export { SessionPicker } from "./components/SessionPicker";
export { PlatformSessionsPage } from "./components/PlatformSessionsPage";
export { usePlatformSessions, useSessions } from "./hooks";
export {
  findPlatform,
  platforms,
  sessionPlatforms,
  sessionsPath,
  type PlatformDefinition,
  type PlatformSlug,
} from "./platforms";
export type {
  SessionCheckResult,
  SessionInfo,
  SessionLaunchResult,
  SessionStatus,
  StoredCookie,
} from "./types";

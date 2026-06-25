import { LayoutDashboard } from "lucide-react";

import { DashboardPage } from "@/components/DashboardPage";
import { registerModule } from "@/lib/modular";

registerModule({
  id: "dashboard",
  order: 0,
  menuFilter: (menu) => [
    {
      label: "Overview",
      items: [
        {
          label: "Dashboard",
          icon: LayoutDashboard,
          path: "/",
        },
      ],
    },
    ...menu,
  ],
  routes: [{ index: true, element: <DashboardPage /> }],
});

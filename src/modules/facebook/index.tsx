import { MessageSquare } from "lucide-react";

import { registerModule } from "@/lib/modular";

function SamplePage() {
  return (
    <div className="flex min-h-0 flex-1 flex-col items-center justify-center p-6">
      <p className="text-sm text-muted-foreground">Sample Page placeholder</p>
    </div>
  );
}

registerModule({
  id: "facebook",
  order: 2,
  menuFilter: (menu) => [
    ...menu,
    {
      label: "Facebook",
      type: ["sessionable"],
      platform: "facebook",
      items: [
        {
          label: "Sample Page",
          icon: MessageSquare,
          path: "/platforms/facebook/sample",
        },
      ],
    },
  ],
  routes: [
    {
      path: "platforms/facebook/sample",
      element: <SamplePage />,
    },
  ],
});

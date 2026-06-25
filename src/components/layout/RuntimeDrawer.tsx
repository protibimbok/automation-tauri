import { useState } from "react";
import { Activity, Globe, PanelRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from "@/components/ui/tabs";
import { useBrowserInstances } from "@/hooks/useBrowserInstances";
import { useRuns } from "@/hooks/useRuns";
import { isActiveRun } from "@/lib/runs";

import { BrowserRuntimePanel } from "./runtime-drawer/BrowserRuntimePanel";
import { TasksRuntimePanel } from "./runtime-drawer/TasksRuntimePanel";
import { taskBrowserInstances } from "./runtime-drawer/utils";

export function RuntimeDrawer() {
  const [open, setOpen] = useState(false);
  const [section, setSection] = useState<"browsers" | "tasks">("tasks");
  const { runs } = useRuns();

  const taskBrowsers = taskBrowserInstances(runs);
  const { instances: browserInstances, registryInstances } =
    useBrowserInstances(taskBrowsers);
  const activeTaskCount = runs.filter(isActiveRun).length;
  const badgeCount = browserInstances.length;

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger
        render={
          <Button
            variant="outline"
            size="sm"
            className="ml-auto cursor-pointer gap-2"
          />
        }
      >
        <PanelRight className="size-4" />
        Runtime
        {badgeCount > 0 && (
          <span className="rounded-full bg-primary px-1.5 py-0.5 text-[10px] font-medium text-primary-foreground">
            {badgeCount}
          </span>
        )}
      </SheetTrigger>
      <SheetContent
        side="right"
        className="flex h-full w-full flex-col gap-0 p-0 sm:max-w-md"
      >
        <SheetHeader className="border-b px-4 py-3">
          <SheetTitle className="flex items-center gap-2">
            <Activity className="size-4" />
            Runtime
          </SheetTitle>
          <SheetDescription>
            Browser instances, sidecar logs, and module task runs.
          </SheetDescription>
        </SheetHeader>

        <Tabs
          value={section}
          onValueChange={(value) => setSection(value as "browsers" | "tasks")}
          className="flex min-h-0 flex-1 flex-col gap-0"
        >
          <div className="border-b px-4 py-3">
            <TabsList className="w-full">
              <TabsTrigger value="browsers" className="flex-1">
                <Globe className="size-3.5" />
                Browsers
                {browserInstances.length > 0 && (
                  <span className="text-xs text-muted-foreground">
                    ({browserInstances.length})
                  </span>
                )}
              </TabsTrigger>
              <TabsTrigger value="tasks" className="flex-1">
                <Activity className="size-3.5" />
                Tasks
                {activeTaskCount > 0 && (
                  <span className="text-xs text-muted-foreground">
                    ({activeTaskCount})
                  </span>
                )}
              </TabsTrigger>
            </TabsList>
          </div>

          <TabsContent value="browsers" className="min-h-0 flex-1" keepMounted>
            <BrowserRuntimePanel
              open={open}
              instances={browserInstances}
              registryInstances={registryInstances}
            />
          </TabsContent>

          <TabsContent value="tasks" className="min-h-0 flex-1" keepMounted>
            <TasksRuntimePanel open={open} onNavigate={() => setOpen(false)} />
          </TabsContent>
        </Tabs>
      </SheetContent>
    </Sheet>
  );
}

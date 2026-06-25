import { BrowserPanel } from "@/components/BrowserPanel";

export function DashboardPage() {
  return (
    <div className="flex min-h-0 flex-1 flex-col gap-6 p-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Launch browser instances and manage automation from here.
        </p>
      </div>
      <BrowserPanel />
    </div>
  );
}

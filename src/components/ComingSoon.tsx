import type { LucideIcon } from "lucide-react";
import { Construction } from "lucide-react";

type ComingSoonProps = {
  title?: string;
  description?: string;
  icon?: LucideIcon;
};

export function ComingSoon({
  title = "Coming soon",
  description = "This section is not available yet.",
  icon: Icon = Construction,
}: ComingSoonProps) {
  return (
    <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-3 p-6 text-center">
      <Icon className="size-10 text-muted-foreground" />
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <p className="max-w-md text-sm text-muted-foreground">{description}</p>
      </div>
    </div>
  );
}

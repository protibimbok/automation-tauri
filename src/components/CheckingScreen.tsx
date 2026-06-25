import { Spinner } from "@/components/ui/spinner";

type CheckingScreenProps = {
  message?: string;
};

export function CheckingScreen({
  message = "Verifying Google Chrome is installed…",
}: CheckingScreenProps) {
  return (
    <main className="flex min-h-svh flex-col items-center justify-center gap-4 p-8">
      <Spinner className="size-8" />
      <div className="flex flex-col items-center gap-1 text-center">
        <h1 className="text-xl font-semibold tracking-tight">Checking setup</h1>
        <p className="text-sm text-muted-foreground">{message}</p>
      </div>
    </main>
  );
}

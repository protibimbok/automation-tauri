import { useEffect, useState } from "react";

import { CheckingScreen } from "@/components/CheckingScreen";
import { MainApp } from "@/components/MainApp";
import { SetupScreen } from "@/components/SetupScreen";
import { BrowserApi } from "@/lib/browser";
import { waitForSidecar } from "@/lib/sidecar";

type SetupPhase = "checking" | "setup" | "ready";

function App() {
  const [phase, setPhase] = useState<SetupPhase>("checking");
  const [checkingMessage, setCheckingMessage] = useState("Starting Python sidecar…");

  useEffect(() => {
    async function bootstrap() {
      try {
        await waitForSidecar();
        setCheckingMessage("Verifying Google Chrome is installed…");
        const result = await BrowserApi.installStatus();
        if (!result.ok) {
          setPhase("setup");
          return;
        }
        setPhase(result.installed ? "ready" : "setup");
      } catch {
        setPhase("setup");
      }
    }

    void bootstrap();
  }, []);

  if (phase === "checking") {
    return <CheckingScreen message={checkingMessage} />;
  }

  if (phase === "setup") {
    return <SetupScreen onReady={() => setPhase("ready")} />;
  }

  return <MainApp />;
}

export default App;

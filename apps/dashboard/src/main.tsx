import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import { Board } from "./Board";
import { Chat } from "./Chat";
import { Guide } from "./Guide";
import "./styles.css";

function App() {
  const [caseId, setCaseId] = useState<string | null>(null);
  const [guide, setGuide] = useState(false);
  if (guide) return <Guide onBack={() => setGuide(false)} />;
  if (!caseId) return <Board onOpen={setCaseId} onGuide={() => setGuide(true)} />;
  return <Chat caseId={caseId} onBack={() => setCaseId(null)} onGuide={() => setGuide(true)} />;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

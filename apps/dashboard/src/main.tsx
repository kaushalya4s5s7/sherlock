import { StrictMode, useState } from "react";
import { createRoot } from "react-dom/client";
import { Board } from "./Board";
import { Chat } from "./Chat";
import "./styles.css";

function App() {
  const [caseId, setCaseId] = useState<string | null>(null);
  if (!caseId) return <Board onOpen={setCaseId} />;
  return <Chat caseId={caseId} onBack={() => setCaseId(null)} />;
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

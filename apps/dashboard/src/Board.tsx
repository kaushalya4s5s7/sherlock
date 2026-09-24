import { useEffect, useState } from "react";
import { health, listCases } from "./api";
import type { CaseRow } from "./types";

function words(value: string) {
  return value.replaceAll("_", " ");
}

function triggerLine(row: CaseRow) {
  if (row.trigger_type === "customer_report" && row.trigger_text) {
    return row.trigger_text.length > 90 ? `${row.trigger_text.slice(0, 90)}…` : row.trigger_text;
  }
  if (row.trigger_type === "analyst_request") return "An analyst asked for this one.";
  return row.risk_score ? `Risk score ${row.risk_score}` : "Risk score";
}

export function Board({ onOpen }: { onOpen: (id: string) => void }) {
  const [rows, setRows] = useState<CaseRow[]>([]);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState("");
  const [note, setNote] = useState("");

  useEffect(() => {
    let cancelled = false;
    health()
      .then((body) => {
        if (!cancelled) setNote(`${body.closed_cases.toLocaleString()} closed cases in memory`);
      })
      .catch(() => {
        if (!cancelled) setError("The case service did not answer.");
      });
    listCases()
      .then((cases) => {
        if (!cancelled) setRows(cases);
      })
      .catch(() => {
        if (!cancelled) setError("The case list did not load.");
      })
      .finally(() => {
        if (!cancelled) setReady(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const alerts = rows.filter((row) => !row.ran);
  const done = rows.filter((row) => row.ran);

  return (
    <main className="board">
      <header className="board-top">
        <div>
          <h1>Case desk</h1>
          <p>New alerts are waiting. Closed history stays in memory and is not investigated again.</p>
        </div>
        <p className="meta">{note}</p>
      </header>
      {error && <p className="error">{error}</p>}
      <section>
        <div className="section-head">
          <h2>New alerts</h2>
          <span>{ready ? alerts.length : ""}</span>
        </div>
        <ul className="table">
          {!ready && <li className="empty">Loading alerts.</li>}
          {alerts.map((row) => (
            <li key={row.case_id}>
              <div>
                <strong>{row.case_id}</strong>
                <span>{row.card_id}</span>
              </div>
              <p>{triggerLine(row)}</p>
              <button type="button" onClick={() => onOpen(row.case_id)}>
                Investigate
              </button>
            </li>
          ))}
          {rows.length > 0 && alerts.length === 0 && <li className="empty">No new alerts.</li>}
        </ul>
      </section>
      <section>
        <div className="section-head">
          <h2>Investigated</h2>
          <span>{ready ? done.length : ""}</span>
        </div>
        <ul className="table done">
          {done.map((row) => (
            <li key={row.case_id}>
              <div>
                <strong>{row.case_id}</strong>
                <span>{row.card_id}</span>
              </div>
              <p>{row.decision ? words(row.decision) : "Opened"}</p>
              <button type="button" className="ghost" onClick={() => onOpen(row.case_id)}>
                Open
              </button>
            </li>
          ))}
          {ready && done.length === 0 && <li className="empty">Nothing investigated in this session yet.</li>}
        </ul>
      </section>
    </main>
  );
}

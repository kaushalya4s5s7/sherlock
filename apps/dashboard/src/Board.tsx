import { useEffect, useState } from "react";
import { health, listCases } from "./api";
import type { CaseResult, CaseRow } from "./types";

const ACTION: Record<string, string> = {
  CREATE_CASE: "Open a case",
  FILE_REPORT: "File a report",
  MONITOR_CARD: "Watch this card",
  MONITOR_CONNECTED_CARDS: "Watch the other cards",
  BLOCK_CARD: "Block this card",
  BLOCK_ALL_CARDS: "Block every card",
  DECLINE_TRANSACTION: "Decline this purchase",
  VERIFY_WITH_CUSTOMER: "Ask the customer",
  ESCALATE_TO_ANALYST: "Send to an analyst",
  WARN_CUSTOMER: "Warn the customer",
  CLOSE_NO_FRAUD: "Close it",
  STEP_UP_AUTH: "Ask for a stronger check",
  ALLOW_TRANSACTION: "Let the purchase through",
};

const VERDICT: Record<string, string> = {
  legitimate: "Real purchase",
  fraud: "Fraud",
  uncertain: "Uncertain",
};

const PATTERN: Record<string, string> = {
  card_not_present_new_device: "Online purchase from a new phone",
  card_not_present_fraud: "Online purchase that may be stolen",
  card_testing: "Tiny test charges",
  out_of_region_use: "Far from the usual places",
  account_takeover: "Someone else on the account",
  undocumented: "A shape with no standard name",
  none: "No named shape",
};

function plan(items: { action: string; route: string }[]) {
  if (!items.length) return "No action";
  return items
    .map((item) => {
      const name = ACTION[item.action] || item.action.replaceAll("_", " ").toLowerCase();
      if (item.route === "L2") return `${name}, a manager must sign`;
      if (item.route === "L1") return `${name}, a team lead must sign`;
      return name;
    })
    .join(". ");
}

function triggerLine(row: CaseRow) {
  if (row.trigger_type === "customer_report" && row.trigger_text) {
    return row.trigger_text.length > 90 ? `${row.trigger_text.slice(0, 90)}…` : row.trigger_text;
  }
  if (row.trigger_type === "analyst_request") return "An analyst asked for this one.";
  return row.risk_score ? `Risk score ${row.risk_score}` : "Risk score";
}

function ResultBrief({ result }: { result: CaseResult }) {
  const same = result.what_changed === "nothing";
  return (
    <div className="result">
      <p>
        <strong>{VERDICT[result.verdict] || result.verdict}</strong>
        {" · "}
        {PATTERN[result.pattern] || result.pattern}
      </p>
      <p>Before extra evidence: {plan(result.initial)}</p>
      <p>After extra evidence: {same ? "Same plan." : plan(result.final)}</p>
      <p>
        {result.sar_file ? "A report is included." : "No report."}{" "}
        {result.written_to_graph ? `Saved in the graph as ${result.graph_case_id}.` : "Not saved in the graph yet."}
      </p>
    </div>
  );
}

export function Board({ onOpen, onGuide }: { onOpen: (id: string) => void; onGuide: () => void }) {
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
          <div className="section-title">
            <h2>New alerts</h2>
            <button type="button" className="ghost" onClick={onGuide}>
              How this works
            </button>
          </div>
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
              {row.result ? <ResultBrief result={row.result} /> : <p>{row.decision || "Opened"}</p>}
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

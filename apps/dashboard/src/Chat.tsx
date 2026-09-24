import { FormEvent, useEffect, useState } from "react";
import { approve, listCases, runCase } from "./api";
import type { Action, CaseRow, Investigation } from "./types";

function money(value: number) {
  return `$${Number(value).toFixed(2)}`;
}

function words(value: string) {
  return value.replaceAll("_", " ");
}

function routeLabel(route: string) {
  if (route === "auto") return "auto";
  if (route === "L1") return "team lead";
  if (route === "L2") return "manager";
  return route;
}

function triggerLine(row: CaseRow) {
  if (row.trigger_type === "customer_report" && row.trigger_text) return row.trigger_text;
  if (row.trigger_type === "analyst_request") return "An analyst asked for this case.";
  return row.risk_score ? `Risk score ${row.risk_score} on ${row.card_id}.` : `Alert on ${row.card_id}.`;
}

function ActionList({ items, approved }: { items: Action[]; approved: string[] }) {
  return (
    <ul className="action-list">
      {items.map((item) => (
        <li key={item.action}>
          <b>{item.action}</b>
          <span>
            {routeLabel(item.route)}
            {approved.includes(item.action) ? " · approved" : ""}
          </span>
        </li>
      ))}
    </ul>
  );
}

export function Chat({ caseId, onBack }: { caseId: string; onBack: () => void }) {
  const [rows, setRows] = useState<CaseRow[]>([]);
  const [result, setResult] = useState<Investigation | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState("");
  const [sent, setSent] = useState(caseId);

  const current = rows.find((row) => row.case_id === sent);

  useEffect(() => {
    let cancelled = false;
    listCases()
      .then((cases) => {
        if (!cancelled) setRows(cases);
      })
      .catch(() => {
        if (!cancelled) setError("The case list did not load.");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    setBusy(true);
    setError("");
    setResult(null);
    runCase(sent)
      .then((body) => {
        if (cancelled) return;
        setResult(body);
        setRows((current) =>
          current.map((row) =>
            row.case_id === sent ? { ...row, ran: true, decision: body.answer.case.verdict } : row,
          ),
        );
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      })
      .finally(() => {
        if (!cancelled) setBusy(false);
      });
    return () => {
      cancelled = true;
    };
  }, [sent]);

  async function sign(action: string) {
    if (!result) return;
    setBusy(true);
    setError("");
    try {
      setResult(await approve(result.answer.case_id, action));
    } catch (err) {
      setError(err instanceof Error ? err.message : "The approval was refused.");
    } finally {
      setBusy(false);
    }
  }

  function send(id: string) {
    const match = rows.find((row) => row.case_id === id);
    if (!match) {
      setError(`${id} is not one of the twenty new alerts.`);
      return;
    }
    setSent(id);
    setDraft("");
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const id = draft.trim().toUpperCase();
    if (id) send(id);
  }

  const suggestions = rows.filter((row) => !row.ran && row.case_id !== sent).slice(0, 3);
  const approved = result?.demo.approved || [];
  const waiting =
    result?.answer.next_best_actions.final.filter((item) => item.route !== "auto" && !approved.includes(item.action)) ||
    [];
  const fired = result?.demo.register.filter((rule) => rule.fired) || [];

  return (
    <main className="chat">
      <header className="chat-top">
        <button type="button" className="ghost" onClick={onBack}>
          Alerts
        </button>
        <strong>{sent}</strong>
      </header>
      <div className="log">
        <div className="bubble user">
          <p>Investigate {sent}.</p>
          {current && <p>{triggerLine(current)}</p>}
        </div>
        {busy && !result && <p className="status">Reading the card, the device, and prior cases.</p>}
        {error && <p className="error">{error}</p>}
        {result && (
          <div className="bubble agent">
            <p className={`verdict ${result.answer.case.verdict}`}>
              {result.answer.case.verdict === "legitimate"
                ? "Looks legitimate"
                : result.answer.case.verdict === "fraud"
                  ? "Treat as fraud"
                  : "Not sure yet"}
              <span>{result.answer.case.fraud_probability.toFixed(2)}</span>
            </p>
            <p>{result.answer.case.summary}</p>
            <h3>Evidence</h3>
            <ul>
              {result.answer.case.evidence.slice(0, 4).map((item) => (
                <li key={item.ref + item.claim}>{item.claim}</li>
              ))}
            </ul>
            {result.answer.case.similar_prior_cases.length > 0 && (
              <p className="fine">Prior cases: {result.answer.case.similar_prior_cases.slice(0, 4).join(", ")}</p>
            )}
            <h3>Before the ask</h3>
            <ActionList items={result.answer.next_best_actions.initial} approved={[]} />
            <h3>After the reply</h3>
            <p className="fine">{result.demo.reply_assumption}</p>
            <ActionList items={result.answer.next_best_actions.final} approved={approved} />
            <p className="fine">
              {result.answer.next_best_actions.what_changed === "nothing"
                ? "The action list did not change."
                : result.answer.next_best_actions.what_changed}
            </p>
            {waiting.length > 0 && (
              <div className="hold">
                {waiting.map((item) => (
                  <button key={item.action} type="button" disabled={busy} onClick={() => void sign(item.action)}>
                    Approve {item.action}
                  </button>
                ))}
              </div>
            )}
            <h3>Rules that fired</h3>
            <ul>
              {fired.map((rule) => (
                <li key={rule.rule}>
                  <b>{rule.rule}</b> {rule.because}
                </li>
              ))}
            </ul>
            <p className="fine">{result.demo.commitment.text}</p>
            <p className="fine">
              {money(result.answer.case.exposure_usd)} exposure. Pattern {words(result.answer.case.pattern)}.
            </p>
            {result.answer.sar.file && <p>{result.answer.sar.narrative}</p>}
          </div>
        )}
      </div>
      <form className="composer" onSubmit={onSubmit}>
        {suggestions.length > 0 && (
          <div className="suggestions">
            {suggestions.map((row) => (
              <button key={row.case_id} type="button" onClick={() => send(row.case_id)}>
                {row.case_id} · {words(row.trigger_type)}
              </button>
            ))}
          </div>
        )}
        <div className="composer-row">
          <input
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="Send another alert, such as HHG-014"
            aria-label="Send an alert"
          />
          <button type="submit" disabled={busy}>
            Send
          </button>
        </div>
      </form>
    </main>
  );
}

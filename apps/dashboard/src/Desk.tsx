import { FormEvent, useEffect, useMemo, useState } from "react";
import { approve, health, listCases, runCase } from "./api";
import type { Action, CaseRow, Investigation } from "./types";

function money(value: number) {
  return `$${value.toFixed(2)}`;
}

function words(value: string) {
  return value.replaceAll("_", " ");
}

function routeLabel(route: string) {
  if (route === "auto") return "the desk may do this";
  if (route === "L1") return "team lead";
  if (route === "L2") return "manager";
  return route;
}

function Actions({ items, approved }: { items: Action[]; approved: string[] }) {
  return (
    <ul className="actions">
      {items.map((item) => (
        <li key={item.action}>
          <b>{item.action}</b>
          <span>
            {routeLabel(item.route)}
            {approved.includes(item.action) ? ", approved" : ""}
          </span>
          <small>{item.reason}</small>
        </li>
      ))}
    </ul>
  );
}

export function Desk({ initialId, onHome }: { initialId: string; onHome: () => void }) {
  const [rows, setRows] = useState<CaseRow[]>([]);
  const [active, setActive] = useState<string | null>(initialId === "list" ? null : initialId);
  const [result, setResult] = useState<Investigation | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState("");
  const [note, setNote] = useState("");

  useEffect(() => {
    let cancelled = false;
    health()
      .then((body) => {
        if (!cancelled) setNote(`${body.transactions.toLocaleString()} transactions in the local graph`);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    listCases()
      .then((cases) => {
        if (cancelled) return;
        setRows(cases);
      })
      .catch((err: Error) => {
        if (!cancelled) setError(err.message);
      });
    if (initialId !== "list") {
      void investigate(initialId);
    }
    return () => {
      cancelled = true;
    };
    // Open the landing choice once. Later cases are chosen from the blotter or the composer.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialId]);

  async function investigate(caseId: string) {
    const known = rows.find((row) => row.case_id === caseId);
    if (rows.length && !known && !/^HHG-\d{3}$/.test(caseId)) {
      setError("This desk investigates HHG-001 through HHG-020.");
      return;
    }
    setActive(caseId);
    setBusy(true);
    setError("");
    setResult(null);
    try {
      const body = await runCase(caseId);
      setResult(body);
      setRows((current) =>
        current.map((row) =>
          row.case_id === caseId ? { ...row, ran: true, decision: body.answer.case.verdict } : row,
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "The investigation stopped.");
    } finally {
      setBusy(false);
    }
  }

  async function sign(action: string) {
    if (!result) return;
    setBusy(true);
    setError("");
    try {
      const body = await approve(result.answer.case_id, action);
      setResult(body);
    } catch (err) {
      setError(err instanceof Error ? err.message : "The approval was refused.");
    } finally {
      setBusy(false);
    }
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const caseId = draft.trim().toUpperCase();
    if (!caseId) return;
    setDraft("");
    const match = rows.find((row) => row.case_id === caseId);
    if (!match) {
      setError(`${caseId} is not one of the twenty exam cases.`);
      return;
    }
    void investigate(caseId);
  }

  const waiting = useMemo(() => {
    if (!result) return [];
    const approved = result.demo.approved || [];
    return result.answer.next_best_actions.final.filter(
      (item) => item.route !== "auto" && !approved.includes(item.action),
    );
  }, [result]);

  const verdict = result?.answer.case.verdict;

  return (
    <div className="desk">
      <aside>
        <button type="button" className="text-button home" onClick={onHome}>
          Back to the openings
        </button>
        <p className="aside-note">{note || "Loading the card history"}</p>
        <div className="blotter">
          {rows.map((row) => (
            <button
              key={row.case_id}
              type="button"
              className={row.case_id === active ? "case on" : "case"}
              onClick={() => void investigate(row.case_id)}
            >
              <strong>
                <i className={row.decision || "idle"} />
                {row.case_id}
              </strong>
              <span>
                {row.card_id}
                <br />
                {words(row.trigger_type)}
                {row.risk_score ? `, score ${row.risk_score}` : ""}
              </span>
            </button>
          ))}
        </div>
      </aside>
      <section className="thread" aria-live="polite">
        <div className="turns">
        {!active && (
          <p className="quiet">Choose a case from the list, or type its id below.</p>
        )}
        {active && (
          <article className="turn you">
            <p>Investigate {active}.</p>
          </article>
        )}
        {busy && !result && <p className="quiet">Reading the card, the device, the region, and the closed cases.</p>}
        {error && <p className="error">{error}</p>}
        {result && (
          <>
            <article className="turn">
              <h2 className={verdict}>{verdict === "legitimate" ? "Looks legitimate" : verdict === "fraud" ? "Treat as fraud" : "Not sure yet"}</h2>
              <p>{result.answer.case.summary}</p>
              <p className="quiet">
                {words(result.demo.trigger)}. {result.demo.history_n} purchases on this card. Pattern{" "}
                {words(result.answer.case.pattern)}. Exposure {money(result.answer.case.exposure_usd)}.
              </p>
            </article>
            <article className="turn">
              <h3>What the graph returned</h3>
              <p>
                {result.demo.flagged.txn_id} for {money(result.demo.flagged.amount)} on {result.demo.flagged.ts},{" "}
                {words(result.demo.flagged.channel)}
                {result.demo.flagged.region ? `, region ${result.demo.flagged.region}` : ""}.
              </p>
              <p>{result.demo.profile || "In person. No device row."}</p>
              <ul className="claims">
                {result.answer.case.evidence.map((item) => (
                  <li key={item.ref + item.claim}>
                    {item.claim}
                    <small>{item.source}</small>
                  </li>
                ))}
              </ul>
              {result.answer.case.similar_prior_cases.length > 0 && (
                <p className="quiet">Prior cases used as memory: {result.answer.case.similar_prior_cases.join(", ")}.</p>
              )}
            </article>
            <article className="turn">
              <h3>How sure the desk is</h3>
              <ol className="waterfall">
                {result.demo.waterfall.map((step) => (
                  <li key={step.name}>
                    <span>{step.name}</span>
                    <b>{step.p.toFixed(2)}</b>
                    <i style={{ width: `${Math.round(step.p * 100)}%` }} />
                  </li>
                ))}
              </ol>
            </article>
            <article className="turn">
              <h3>Before any further evidence</h3>
              <Actions items={result.answer.next_best_actions.initial} approved={[]} />
              <h3>After the assumed reply</h3>
              <p>{result.demo.reply_assumption}</p>
              <Actions items={result.answer.next_best_actions.final} approved={result.demo.approved || []} />
              <p className="quiet">
                {result.answer.next_best_actions.what_changed === "nothing"
                  ? "The action list did not change."
                  : result.answer.next_best_actions.what_changed}
              </p>
              {waiting.length > 0 && (
                <div className="hold">
                  <p>These stay here until you approve them.</p>
                  {waiting.map((item) => (
                    <button key={item.action} type="button" disabled={busy} onClick={() => void sign(item.action)}>
                      Approve {item.action}
                    </button>
                  ))}
                </div>
              )}
              {waiting.length === 0 && (
                <p className="quiet">
                  {result.demo.approval === "approved"
                    ? "Approved. That action can go out."
                    : "Nothing here needs a person. Auto actions are already allowed."}
                </p>
              )}
            </article>
            <article className="turn">
              <h3>Rules</h3>
              <ul className="rules">
                {result.demo.register.map((rule) => (
                  <li key={rule.rule} className={rule.fired ? "fired" : ""}>
                    <b>{rule.rule}</b>
                    <span>{rule.fired ? rule.because : "Did not fire"}</span>
                  </li>
                ))}
              </ul>
            </article>
            <article className="turn">
              <h3>If the reply had been different</h3>
              <p className="quiet">Not what happened.</p>
              <ul className="claims">
                {result.demo.counterfactuals.map((item) => (
                  <li key={item.reply}>
                    {item.reply} would have led to {item.actions.join(", ")} at {item.p.toFixed(2)}.
                  </li>
                ))}
              </ul>
              <h3>Why the desk stopped</h3>
              <p>{result.demo.commitment.text}</p>
              <p className="quiet">{result.answer.stop_reason}</p>
              {result.answer.sar.file && (
                <>
                  <h3>Suspicious activity report</h3>
                  <p>{result.answer.sar.narrative}</p>
                </>
              )}
              <p className="quiet">
                {result.answer.case.written_to_graph
                  ? `Saved as ${result.answer.case.graph_case_id} and read back.`
                  : `Recorded locally as ${result.answer.case.graph_case_id}. The TigerGraph flag stays off until a live read-back matches.`}
              </p>
            </article>
          </>
        )}
        </div>
        <form className="composer" onSubmit={onSubmit}>
          <label htmlFor="ask">Open a case</label>
          <input
            id="ask"
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            placeholder="HHG-014"
            autoComplete="off"
          />
          <button type="submit" disabled={busy}>
            Investigate
          </button>
        </form>
      </section>
    </div>
  );
}

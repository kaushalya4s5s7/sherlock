import { FormEvent, useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { approve, caseProgress, closedCase, listCases, openCase, type PipelineStep } from "./api";
import { Neighborhood } from "./Neighborhood";
import portrait from "./assets/investigator.png";
import type { Action, CaseRow, ClosedCase, Investigation } from "./types";

function money(value: number) {
  return `$${Number(value).toFixed(2)}`;
}

function words(value: string) {
  return value.replaceAll("_", " ");
}

const ACTION: Record<string, string> = {
  CREATE_CASE: "Open a case",
  FILE_REPORT: "File a report",
  MONITOR_CARD: "Watch this card",
  MONITOR_CONNECTED_CARDS: "Watch the other cards on this device",
  BLOCK_CARD: "Block this card",
  BLOCK_ALL_CARDS: "Block every card on this account",
  DECLINE_TRANSACTION: "Decline this purchase",
  VERIFY_WITH_CUSTOMER: "Ask the customer",
  ESCALATE_TO_ANALYST: "Send this to an analyst",
  WARN_CUSTOMER: "Warn the customer",
  CLOSE_NO_FRAUD: "Close it. This is not fraud",
  STEP_UP_AUTH: "Ask for a stronger check",
};

const PATTERN: Record<string, string> = {
  card_not_present_new_device: "An online purchase from a new device",
  card_not_present_fraud: "An online purchase that may be stolen",
  card_testing: "Tiny charges used to test the card",
  out_of_region_use: "A purchase far from where this card is usually used",
  account_takeover: "Someone else may be using the account",
  undocumented: "A fraud shape we do not have a standard name for",
  none: "No fraud pattern",
  insufficient: "Not enough to name a pattern",
};

const FAMILY: Record<string, string> = {
  device: "the phone or computer",
  sequence: "the pattern of amounts",
  region: "the location",
  recurring: "the regular monthly charge",
  prior_case: "the older cases",
  customer_reply: "the customer's answer",
};

const STEP_TITLE: Record<string, string> = {
  intake: "Open this alert",
  pack: "Look up the card, the device, and older cases",
  pattern: "Say what kind of fraud this looks like",
  hop: "Decide if one more lookup would help",
  pass1: "Decide what to do before asking the customer",
  reply: "Use the one answer we would expect from the customer",
  pass2: "Decide what we will actually do",
  prose: "Write the summary from what we found",
  approval: "Wait if a person must sign off",
  memory: "Save the case and check that it saved",
};

function plainAction(name: string) {
  return ACTION[name] || name.replaceAll("_", " ").toLowerCase();
}

function plainPattern(name: string) {
  return PATTERN[name] || name.replaceAll("_", " ");
}

function routeLabel(route: string, approved: boolean) {
  if (approved && route === "L2") return "A manager approved this";
  if (approved && route === "L1") return "A team lead approved this";
  if (approved) return "Approved";
  if (route === "auto") return "Happens on its own";
  if (route === "L1") return "A team lead must approve";
  if (route === "L2") return "A manager must approve";
  return route;
}

function chance(value: number) {
  return `${Math.round(value * 100)}% chance this is fraud`;
}

function marketRead(verdict: string, p: number) {
  const percent = Math.round(p * 100);
  if (verdict === "legitimate") return "Let it through. No extra check, and no block.";
  if (verdict === "fraud") return "Call it fraud. A block or a report still waits for a signature. Nothing else does.";
  if (p >= 0.7) return `${percent}% leans toward fraud. Add a check and keep the card open. Do not call it fraud yet.`;
  if (p >= 0.3) return `${percent}% is the middle. Ask for a stronger check. Do not block.`;
  return `${percent}% is low. Let it through and watch the card.`;
}

function soften(text: string) {
  return text
    .replaceAll("device profile", "device")
    .replaceAll("Jev", "The decision model")
    .replaceAll(/\bp (\d+\.\d+)/g, (_, raw: string) => chance(Number(raw)))
    .replaceAll("Fraud probability is ", "The chance of fraud is ")
    .replaceAll("billing region not recorded", "no billing region on file")
    .replaceAll("Flagged ", "Purchase ")
    .replaceAll("Closed cases guided the search and are not treated as proof by themselves.", "Older cases helped the search. They do not prove this charge.")
    .replaceAll("The report is filed because the final action list includes FILE_REPORT.", "A report is included because that is one of the actions.")
    .replaceAll("Suspicious amount on the affected transactions is", "The amount in question is")
    .replaceAll("FILE_REPORT", "file a report")
    .replaceAll("CREATE_CASE", "open a case")
    .replaceAll("MONITOR_CONNECTED_CARDS", "watch the other cards on this device")
    .replaceAll("MONITOR_CARD", "watch this card");
}

function plainCommitment(text: string) {
  const drop = text.match(/^Drop the (.+) evidence and the action list changes/i);
  if (drop) {
    const family = FAMILY[drop[1].replaceAll(" ", "_")] || drop[1];
    return `If we ignore ${family}, we would do something different. That is what this decision rests on.`;
  }
  if (text.startsWith("No single family")) {
    return "No one fact, on its own, would change what we do. The decision comes from the combination.";
  }
  return soften(text);
}

function spoken(name: string) {
  if (name === "file a report") return "the report";
  return name;
}

function listOf(items: string[]) {
  if (items.length <= 1) return items[0] || "";
  return `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`;
}

function nextStep(result: Investigation, waiting: Action[], approved: string[]) {
  const percent = Math.round(result.answer.case.fraud_probability * 100);
  const automatic = result.answer.next_best_actions.final
    .filter((item) => item.route === "auto")
    .map((item) => plainAction(item.action).toLowerCase());
  const onItsOwn = automatic.length ? `On its own it will ${listOf(automatic)}.` : "";

  if (waiting.length > 0) {
    const names = listOf(waiting.map((item) => spoken(plainAction(item.action).toLowerCase())));
    return {
      you: `Your part: approve ${names}. That is the only thing waiting on a person.`,
      agent: `The agent will not block the card. ${percent}% is a lean, and we are still not sure. ${onItsOwn}`,
    };
  }
  if (result.answer.case.verdict === "legitimate") {
    return {
      you: "Your part is finished. Nothing to sign.",
      agent: "The agent leaves the card open. This looks like a real purchase.",
    };
  }
  if (result.answer.case.verdict === "fraud") {
    return {
      you: "Your part is finished. Nothing else to sign.",
      agent: `The agent treats this as fraud. ${onItsOwn}`,
    };
  }
  const signed = approved.map((name) => spoken(plainAction(name).toLowerCase()));
  const you = signed.length
    ? `Your part is finished. You signed ${listOf(signed)}.`
    : "Your part is finished. Nothing was waiting on a person.";
  return {
    you,
    agent: `The agent will not block the card. ${percent}% leans toward fraud, and that is not sure enough. ${onItsOwn} Go back to the other alerts.`,
  };
}

function plainWhy(text: string) {
  const after = text.includes(": ") ? text.split(": ").slice(1).join(": ") : text;
  const sentence = after.trim();
  return sentence.charAt(0).toUpperCase() + sentence.slice(1);
}

function triggerLine(row: CaseRow) {
  if (row.trigger_type === "customer_report" && row.trigger_text) return customerWords(row.trigger_text);
  if (row.trigger_type === "analyst_request") return "An analyst asked for this case.";
  return row.risk_score ? `Risk score ${row.risk_score} on ${row.card_id}.` : `Alert on ${row.card_id}.`;
}

function answerQuestion(text: string, result: Investigation) {
  const q = text.toLowerCase();
  const file = result.answer;
  const card = file.case;
  const final = file.next_best_actions.final;
  const names = final.map((item) => plainAction(item.action)).join(", ");
  const reasons = final.map((item) => `${plainAction(item.action)}: ${item.reason}`).join(" ");
  const claims = card.evidence.map((item) => soften(item.claim)).slice(0, 4).join(" ");
  const fired = result.demo.register.filter((rule) => rule.fired).map((rule) => plainWhy(rule.because));
  const verdict =
    card.verdict === "legitimate"
      ? "this looks like a real purchase"
      : card.verdict === "fraud"
        ? "treat this as fraud"
        : "we are not sure yet";

  const parts: string[] = [];
  const ask = (pattern: RegExp) => pattern.test(q);

  if (ask(/probab|score|sure|verdict|fraud|legit|risk|why/)) {
    parts.push(`${verdict}. ${chance(card.fraud_probability)}. ${card.pattern_description || card.summary}`);
  }
  if (ask(/why|rule|policy|because|what should|recommend|action|block|decline|monitor|next|do now/)) {
    parts.push(fired.length ? fired.join(" ") : reasons);
    parts.push(`What we will do: ${names}.`);
  }
  if (ask(/money|exposure|amount|dollar|how much/)) {
    parts.push(
      card.verdict === "legitimate"
        ? "No money is at risk. This looks like a real purchase."
        : `${money(card.exposure_usd)} is at risk across ${card.affected_txn_ids.length} purchase${card.affected_txn_ids.length === 1 ? "" : "s"}.`,
    );
  }
  if (ask(/pattern|kind of|type of|device|ring/)) {
    const shape = card.pattern_description || result.demo.pattern_description;
    parts.push(`${plainPattern(card.pattern)}. ${shape} ${result.demo.profile ? `Device: ${result.demo.profile}.` : ""}`);
  }
  if (ask(/evidence|what happened|claim|fact/)) parts.push(claims || card.summary);
  if (ask(/prior|similar|old case|memory|earlier/)) {
    parts.push(
      card.similar_prior_cases.length
        ? `Older cases we looked at: ${card.similar_prior_cases.slice(0, 6).join(", ")}. They helped the search. They do not prove this charge.`
        : "No older case looked like this one.",
    );
  }
  if (ask(/stop|enough|finished/)) parts.push(plainCommitment(file.stop_reason));
  if (ask(/chang|before|after|reply|assum/)) {
    const changed = file.next_best_actions.what_changed;
    parts.push(`${result.demo.reply_assumption} ${changed === "nothing" ? "The action list did not change." : changed}`);
  }
  if (ask(/approv|sign|manager|team lead/)) {
    const waiting = final
      .filter((item) => item.route !== "auto")
      .map((item) => `${plainAction(item.action)}: ${routeLabel(item.route, false)}`);
    parts.push(waiting.length ? `${waiting.join(". ")}.` : "Nothing is waiting for a person. The rest happens on its own.");
  }
  if (ask(/report|sar|regulat/)) {
    parts.push(
      file.sar.file
        ? `A report should be filed. ${file.sar.reason || ""} ${file.sar.narrative}`
        : "No report. Filing a report is not one of the actions.",
    );
  }
  if (parts.length === 0) {
    parts.push(
      `${verdict}. ${chance(card.fraud_probability)}. ${card.pattern_description || soften(card.summary)} What we will do: ${names}.`,
    );
  }
  return parts.join(" ");
}

const OPENING: PipelineStep[] = [
  { id: "intake", label: "Open the alert", detail: "", status: "running" },
  { id: "pack", label: "Read the card, the device, and prior cases", detail: "", status: "waiting" },
  { id: "pattern", label: "Name the pattern", detail: "", status: "waiting" },
  { id: "hop", label: "Choose one more graph lookup", detail: "", status: "waiting" },
  { id: "pass1", label: "Choose actions before any reply", detail: "", status: "waiting" },
  { id: "reply", label: "Assume the one customer answer", detail: "", status: "waiting" },
  { id: "pass2", label: "Set the final actions", detail: "", status: "waiting" },
  { id: "prose", label: "Write the summary from the evidence", detail: "", status: "waiting" },
  { id: "approval", label: "Hold a signature when one is required", detail: "", status: "waiting" },
  { id: "memory", label: "Write the case and read it back", detail: "", status: "waiting" },
];

function customerWords(text: string) {
  const quoted = text.match(/'([^']+)'/);
  if (quoted) return quoted[1];
  return text.replace(/^Customer \S+ message:\s*/i, "").replace(/\s*Refers to \d+\.?/g, "");
}

function plainPurchase(claim: string) {
  const amount = claim.match(/\$[\d,.]+/);
  const when = claim.match(/on (\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2}:\d{2})?)/);
  if (!amount) return soften(claim);
  return `The purchase they asked about is ${amount[0]}${when ? ` on ${when[1]}` : ""}.`;
}

function plainClaim(claim: string) {
  const text = soften(claim);
  if (/Build\/|device marked|chrome \d|for android/i.test(text)) {
    return "This purchase came from a phone or computer this card has not used before.";
  }
  if (/Customer \S+ message|Refers to \d+/i.test(text)) return customerWords(text);
  if (/share this device/i.test(text)) return text.replace("device", "phone or computer");
  if (/Purchase \d+/.test(text) && /\$\d/.test(text)) return plainPurchase(text);
  return text;
}

function UserReport({ result, row }: { result: Investigation; row?: CaseRow }) {
  const said = row?.trigger_type === "customer_report" ? customerWords(row.trigger_text) : "";
  const purchase = result.answer.case.evidence.map((item) => item.claim).find((claim) => /\$\d/.test(claim));
  if (!said && !result.answer.sar.file) return null;
  return (
    <section className="user-report">
      <h3>The report</h3>
      {said ? <p className="summary">{said}</p> : <p className="summary">The customer did not write in. This note is about the charge below.</p>}
      {purchase && <p className="summary">{plainPurchase(purchase)}</p>}
    </section>
  );
}

function Pipeline({ steps }: { steps: PipelineStep[] }) {
  return (
    <ol className="pipeline">
      {steps.map((step) => (
        <li key={step.id} className={step.status}>
          <span className="mark" />
          <span>
            <span className="step-title">{STEP_TITLE[step.id] || step.label}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}

function outcomeLabel(outcome: string) {
  if (outcome === "confirmed_fraud") return "Confirmed fraud";
  if (outcome === "cleared") return "Cleared";
  return words(outcome);
}

function PriorCases({ ids, onOpen }: { ids: string[]; onOpen: (id: string) => void }) {
  const shown = ids.slice(0, 4);
  return (
    <p className="fine">
      Older cases we looked at:{" "}
      {shown.map((id, index) => (
        <span key={id}>
          {index > 0 ? ", " : ""}
          <button type="button" className="case-link" onClick={() => onOpen(id)}>
            {id}
          </button>
        </span>
      ))}
    </p>
  );
}

function CaseForm({
  record,
  busy,
  error,
  onClose,
}: {
  record: ClosedCase | null;
  busy: boolean;
  error: string;
  onClose: () => void;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="sheet-back" onClick={onClose}>
      <section
        className="sheet"
        role="dialog"
        aria-modal="true"
        aria-labelledby="closed-case-title"
        onClick={(event) => event.stopPropagation()}
      >
        <header className="sheet-top">
          <h2 id="closed-case-title">{record?.case_id || "Older case"}</h2>
          <button ref={closeRef} type="button" className="text-btn" onClick={onClose}>
            Close
          </button>
        </header>
        {busy && <p className="fine">Opening the closed case.</p>}
        {error && <p className="error">{error}</p>}
        {record && (
          <>
            <p className={`verdict ${record.outcome === "confirmed_fraud" ? "fraud" : "legitimate"}`}>
              {outcomeLabel(record.outcome)}
              <span>{plainPattern(record.pattern)}</span>
            </p>
            <p className="facts">
              <span>{record.card_id}</span>
              <span>{record.customer_id}</span>
              <span>{record.exposure_usd > 0 ? `${money(record.exposure_usd)} exposure` : "No exposure"}</span>
            </p>
            {record.actions.length > 0 && (
              <>
                <h3>What was done</h3>
                <ul className="action-list">
                  {record.actions.map((action) => (
                    <li key={action}>
                      <b>{plainAction(action)}</b>
                    </li>
                  ))}
                </ul>
              </>
            )}
            {record.notes && (
              <>
                <h3>Analyst notes</h3>
                <p className="summary">{record.notes}</p>
              </>
            )}
            {record.txn_ids.length > 0 && (
              <p className="fine">Purchases: {record.txn_ids.join(", ")}</p>
            )}
            {record.connected.length > 0 && (
              <p className="fine">Other cards: {record.connected.join(", ")}</p>
            )}
          </>
        )}
      </section>
    </div>
  );
}

function Investigator({ children }: { children: ReactNode }) {
  return (
    <div className="turn agent">
      <img className="face" src={portrait} alt="" />
      <div className="bubble agent">{children}</div>
    </div>
  );
}

const STEP_NAME: Record<string, string> = {
  "risk score prior": "The bank's own score",
  "new device": "A phone we have not seen",
  "shared with a confirmed case": "That phone was in an older fraud case",
  "long quiet history": "The card has been quiet",
  "card testing": "Tiny test charges",
  "structuring cluster": "Several charges just under $500",
  "shared proxy device": "A shared hidden phone",
  "anonymous proxy": "A hidden connection",
  "new region": "A place this card has not used",
  "home region": "The card's usual place",
  "travel shape": "A trip, with home charges still happening",
  "monthly subscription": "A charge that matches a monthly payment",
  "customer denies the purchase": "The customer says it was not theirs",
  "customer confirms the purchase": "The customer says it was theirs",
  "no reply in 24 hours": "No answer from the customer",
  "prior from memory": "Older cases like this one",
};

const LOOKUP: Record<string, string> = {
  component_cards: "We looked at the other cards on this phone.",
  community_lookup: "We walked the wider group of cards that share a phone.",
  prior_cases: "We looked again at older cases.",
  policy_passage: "We read the closest policy note stored with the charges.",
  none: "We did not take an extra lookup.",
};

function ChanceLine({ steps }: { steps: { name: string; delta: number; p: number }[] }) {
  const width = 560;
  const height = 148;
  const padX = 28;
  const padY = 16;
  const points = steps.map((step, index) => {
    const x = padX + (index / Math.max(steps.length - 1, 1)) * (width - padX * 2);
    const y = height - padY - step.p * (height - padY * 2);
    return { ...step, x, y };
  });
  const line = points.map((point, index) => `${index ? "L" : "M"}${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");
  const mid = height - padY - 0.7 * (height - padY * 2);
  return (
    <figure className="curve">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="How the chance moved on this case">
        <line className="guide" x1={padX} y1={mid} x2={width - padX} y2={mid} />
        <path d={line} />
        {points.map((point) => (
          <circle key={point.name} cx={point.x} cy={point.y} r="4" />
        ))}
      </svg>
      <ol>
        {steps.map((step) => (
          <li key={step.name}>
            <span>{STEP_NAME[step.name] || step.name}</span>
            <span>{Math.round(step.p * 100)}%</span>
          </li>
        ))}
      </ol>
    </figure>
  );
}

function CaseTechniques({ result, cardId }: { result: Investigation; cardId?: string }) {
  const pattern = result.answer.case.pattern;
  const lost = result.demo.why_not || [];
  const matched = pattern !== "none" && pattern !== "insufficient";
  const fired = result.demo.register.filter((rule) => rule.fired);
  const lookup = LOOKUP[result.demo.hop || "none"] || "We did not take an extra lookup.";
  const locked = lost.some((item) => /did not fire/i.test(item.reason));
  return (
    <section className="techniques">
      <h3>How this report was built</h3>
      <p className="fine">These are the checks that ran on this charge. The picture uses this case, not a sample.</p>

      <h3>Pattern match</h3>
      <p className="fine">
        {matched
          ? "Five known shapes were checked. One fit, and that is the name we kept."
          : "Five known shapes were checked. None fit this charge, so the name stays blank. A new phone by itself is not enough to force a name."}
      </p>
      <ul className="match">
        {matched && (
          <li className="hit">
            <span>{plainPattern(pattern)}</span>
            <i style={{ width: "100%" }} />
            <em>This is the shape</em>
          </li>
        )}
        {lost.map((item) => (
          <li key={item.pattern} className="checked">
            <span>{plainPattern(item.pattern)}</span>
            <em>
              {pattern === "card_not_present_new_device" && item.pattern === "card_not_present_fraud"
                ? "Seen. The new-phone shape is more specific, so we kept that."
                : "Checked. Not this shape."}
            </em>
          </li>
        ))}
      </ul>

      <h3>How the chance moved</h3>
      <p className="fine">Each fact on this charge moves the line. The dashed line is 70%. Under it, one weak sign is not a block.</p>
      {result.demo.waterfall.length > 0 && <ChanceLine steps={result.demo.waterfall} />}

      <h3>What the graph connected</h3>
      <Neighborhood result={result} cardId={cardId} />
      <p className="fine">
        {result.demo.history_n > 0 ? `${result.demo.history_n.toLocaleString()} earlier charges on this card. ` : ""}
        {lookup}{" "}
        {result.answer.case.similar_prior_cases.length > 0
          ? `${result.answer.case.similar_prior_cases.length} older cases helped the search. They do not prove this charge.`
          : "No older case looked like this one."}
      </p>

      <h3>Jev on this case</h3>
      <p className="summary">
        Jev, jev-1.13-free, is the model we call for three checks: name the pattern, allow one extra lookup, and drop a sentence that adds a fact.{" "}
        {locked
          ? "A fixed check already named the pattern, so Jev was not asked to rename it. "
          : "The fixed check had not locked a name, so Jev was asked. "}
        {result.demo.control_fallback
          ? "A check Jev did not answer is recorded on this case. That backup did not choose the actions."
          : "Jev answered those checks. The rules still chose the actions."}
      </p>

      {fired.length > 0 && (
        <>
          <h3>Rules that applied</h3>
          <ul className="steps">
            {fired.map((rule) => (
              <li key={rule.rule}>
                {rule.rule}. {plainWhy(rule.because)}
              </li>
            ))}
          </ul>
          <p className="fine">The other rules were checked and did not apply to this charge.</p>
        </>
      )}
    </section>
  );
}

function ActionList({ items, approved }: { items: Action[]; approved: string[] }) {
  return (
    <ul className="action-list">
      {items.map((item) => (
        <li key={item.action}>
          <b>{plainAction(item.action)}</b>
          <span>{routeLabel(item.route, approved.includes(item.action))}</span>
        </li>
      ))}
    </ul>
  );
}

export function Chat({ caseId, onBack, onGuide }: { caseId: string; onBack: () => void; onGuide: () => void }) {
  const [rows, setRows] = useState<CaseRow[]>([]);
  const [result, setResult] = useState<Investigation | null>(null);
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState("");
  const [draft, setDraft] = useState("");
  const [sent, setSent] = useState(caseId);
  const [notes, setNotes] = useState<{ who: "user" | "agent"; text: string }[]>([]);
  const [steps, setSteps] = useState<PipelineStep[]>(OPENING);
  const [prior, setPrior] = useState<ClosedCase | null>(null);
  const [priorOpen, setPriorOpen] = useState(false);
  const [priorBusy, setPriorBusy] = useState(false);
  const [priorError, setPriorError] = useState("");
  const logRef = useRef<HTMLDivElement>(null);
  const waitingQuestion = useRef<string | null>(null);

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
    setNotes([]);
    setSteps(OPENING);
    waitingQuestion.current = null;
    openCase(sent)
      .then((body) => {
        if (cancelled) return;
        setResult(body);
        const asked = waitingQuestion.current;
        if (asked) {
          waitingQuestion.current = null;
          setNotes((current) => [...current, { who: "agent", text: answerQuestion(asked, body) }]);
        }
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

  const closePrior = useCallback(() => setPriorOpen(false), []);

  function openPrior(id: string) {
    const exam = id.startsWith("EXAM-") ? id.slice(5) : id;
    if (exam.startsWith("HHG-")) {
      send(exam);
      return;
    }
    setPrior(null);
    setPriorOpen(true);
    setPriorBusy(true);
    setPriorError("");
    closedCase(id)
      .then(setPrior)
      .catch((err: Error) => setPriorError(err.message))
      .finally(() => setPriorBusy(false));
  }

  function send(id: string) {
    const match = rows.find((row) => row.case_id === id);
    if (!match) {
      setError(`${id} is not one of the twenty new alerts.`);
      return;
    }
    setSent(id);
    setDraft("");
    setError("");
  }

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const text = draft.trim();
    if (!text) return;
    const id = text.toUpperCase().match(/HHG-\d{3}/);
    const onlyId = id && text.replace(id[0], "").trim().length === 0;
    const openId = id && /^(investigate|open|send|look at)\s+hhg-\d{3}$/i.test(text);
    if (id && (onlyId || openId)) {
      send(id[0]);
      return;
    }
    setError("");
    setDraft("");
    if (!result) {
      waitingQuestion.current = text;
      setNotes((current) => [
        ...current,
        { who: "user", text },
        { who: "agent", text: `${sent} is still being read. The answer will follow as soon as the case is on screen.` },
      ]);
      return;
    }
    setNotes((current) => [
      ...current,
      { who: "user", text },
      { who: "agent", text: answerQuestion(text, result) },
    ]);
  }

  useEffect(() => {
    if (!busy && !result) return;
    let cancelled = false;
    const look = () => {
      caseProgress(sent)
        .then((next) => {
          if (!cancelled) setSteps(next);
        })
        .catch(() => undefined);
    };
    look();
    if (result) {
      return () => {
        cancelled = true;
      };
    }
    const timer = window.setInterval(look, 1000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [busy, result, sent]);

  useEffect(() => {
    const log = logRef.current;
    if (!log) return;
    const current = log.querySelector(".pipeline li.running");
    if (current && busy && !result) {
      current.scrollIntoView({ block: "center" });
      return;
    }
    log.scrollTop = log.scrollHeight;
  }, [notes, result, busy, steps]);

  const suggestions = rows.filter((row) => !row.ran && row.case_id !== sent).slice(0, 3);
  const approved = result?.demo.approved || [];
  const waiting =
    result?.answer.next_best_actions.final.filter((item) => item.route !== "auto" && !approved.includes(item.action)) ||
    [];
  const step = result ? nextStep(result, waiting, approved) : null;

  return (
    <main className="desk">
      <header className="bar">
        <div className="bar-actions">
          <button type="button" className="text-btn" onClick={onBack}>
            Alerts
          </button>
          <button type="button" className="text-btn" onClick={onGuide}>
            How this works
          </button>
        </div>
        <p className="bar-title">{sent}</p>
      </header>
      <div className="stage" ref={logRef}>
        <div className="thread">
          <div className="turn user">
            <div className="bubble user">
              <p>Investigate {sent}.</p>
              {current && <p>{triggerLine(current)}</p>}
            </div>
          </div>
          {busy && !result && (
            <Investigator>
              <Pipeline steps={steps} />
            </Investigator>
          )}
          {error && <p className="error">{error}</p>}
          {result && (
            <Investigator>
              <Pipeline steps={steps} />
              <p className={`verdict ${result.answer.case.verdict}`}>
                {result.answer.case.verdict === "legitimate"
                  ? "This looks like a real purchase"
                  : result.answer.case.verdict === "fraud"
                    ? "Treat this as fraud"
                    : "We are not sure yet"}
                <span>{chance(result.answer.case.fraud_probability)}</span>
              </p>
              <p className="fine">{marketRead(result.answer.case.verdict, result.answer.case.fraud_probability)}</p>
              {step && (
                <div className="next-step">
                  <p>{step.you}</p>
                  <p>{step.agent}</p>
                </div>
              )}
              <p className="summary">{plainPattern(result.answer.case.pattern)}</p>
              <p className="facts">
                <span>
                  {result.answer.case.exposure_usd > 0
                    ? `${money(result.answer.case.exposure_usd)} at risk`
                    : "No money at risk"}
                </span>
                <span>{plainPattern(result.answer.case.pattern)}</span>
              </p>
              <h3>What we will do</h3>
              <ActionList items={result.answer.next_best_actions.final} approved={approved} />
              {waiting.length > 0 && (
                <div className="hold">
                  {waiting.map((item) => (
                    <button key={item.action} type="button" disabled={busy} onClick={() => void sign(item.action)}>
                      Approve: {plainAction(item.action).toLowerCase()}
                    </button>
                  ))}
                </div>
              )}
              <UserReport result={result} row={current} />
              <CaseTechniques result={result} cardId={current?.card_id} />
              <h3>What we found</h3>
              <ul className="steps">
                {result.answer.case.evidence.slice(0, 4).map((item) => (
                  <li key={item.ref + item.claim}>{plainClaim(item.claim)}</li>
                ))}
              </ul>
              <h3>The earlier plan</h3>
              <p className="fine">
                This is what we would have done before we finished. It is not another task, and the report in this list is not waiting for a second signature.
              </p>
              <ActionList items={result.answer.next_best_actions.initial} approved={[]} />
              <p className="fine">
                {result.demo.reply_assumption ===
                "No question was sent. The stop rule was already met, or R7 carried the dispute."
                  ? "We did not ask the customer. We already had enough to decide, or they were disputing a charge that matches their usual payments."
                  : soften(result.demo.reply_assumption)}
              </p>
              <p className="fine">
                {result.answer.next_best_actions.what_changed === "nothing"
                  ? "Asking the customer would not change what we do."
                  : soften(result.answer.next_best_actions.what_changed)}
              </p>
              {result.answer.case.similar_prior_cases.length > 0 && (
                <PriorCases ids={result.answer.case.similar_prior_cases} onOpen={openPrior} />
              )}
              <h3>What this decision rests on</h3>
              <p className="summary">{plainCommitment(result.demo.trace?.anomaly || result.demo.commitment.text)}</p>
            </Investigator>
          )}
          {notes.map((note, index) =>
            note.who === "user" ? (
              <div key={`${note.who}-${index}`} className="turn user">
                <div className="bubble user">
                  <p>{note.text}</p>
                </div>
              </div>
            ) : (
              <Investigator key={`${note.who}-${index}`}>
                <p className="summary">{note.text}</p>
              </Investigator>
            ),
          )}
        </div>
      </div>
      <form className="dock" onSubmit={onSubmit}>
        {!busy && suggestions.length > 0 && (
          <div className="suggestions">
            {suggestions.map((row) => (
              <button key={row.case_id} type="button" onClick={() => send(row.case_id)}>
                {row.case_id}
                <span>{words(row.trigger_type)}</span>
              </button>
            ))}
          </div>
        )}
        <div className="composer-card">
          <div className="composer-input">
            <input
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              placeholder="How should this case be read?"
              aria-label="Ask about this case"
              autoComplete="off"
            />
            <button type="submit" className="send" aria-label="Send">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M4 12h14M13 6l6 6-6 6" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
          </div>
          <div className="composer-meta">
            <span className="speaker">
              <img src={portrait} alt="" />
              Investigator
            </span>
            <span>{sent}</span>
          </div>
        </div>
      </form>
      {priorOpen && (
        <CaseForm
          record={prior}
          busy={priorBusy}
          error={priorError}
          onClose={closePrior}
        />
      )}
    </main>
  );
}

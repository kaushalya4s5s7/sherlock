const STEPS = [
  ["Open the alert", "One charge starts the case. Nothing is decided yet."],
  ["Look up the card", "Recent charges, the phone or computer, and older cases."],
  ["Name the shape", "A fixed check names it when the shape is clear. Otherwise Jev names it."],
  ["One more look, or stop", "Jev allows at most one extra lookup, or none."],
  ["A first plan", "What we would do before any answer from the customer."],
  ["One expected answer", "If we need the customer, we assume one answer from the facts."],
  ["The plan we will use", "The rules run again. The first plan stays beside it."],
  ["A short note", "The paragraph is written from facts we already have. Jev drops a sentence that adds a new fact."],
  ["A signature, when one is needed", "A block, a decline, or a report waits for a person."],
  ["Save, then read it back", "The result counts only when the saved copy matches."],
];

const RULES = [
  ["R1", "One weak sign, and the chance under 70%", "Ask the customer or ask for a stronger check before any block."],
  ["R2", "The customer says the charge was not theirs", "Block the card and open a case. A complaint by itself is not this."],
  ["R3", "The customer says the charge was theirs", "Close the case. Leave the card open."],
  ["R4", "We asked, and nobody answered", "Watch the card and decline that purchase."],
  ["R5", "Several tiny online charges, then a larger one", "Decline the purchase and ask for a stronger check. A large charge that already went through can mean a block."],
  ["R6", "The same phone shows fraud on more than one card", "Open a case, file a report, and watch the other cards. Sharing a phone with quiet cards is not enough."],
  ["R7", "The customer disputes a charge that matches their usual monthly payment", "This runs before a block. Open a case, ask them, and warn them. Do not block."],
  ["R8", "Still unsure, and the money is over $500, or the facts disagree", "Send it to an analyst. Do not block just because we are unsure."],
  ["R9", "A fraud shape the bank never named, touching more than one customer", "Open a case, file a report, and send it to an analyst. Do not rename it as an ordinary online purchase."],
  ["R10", "Block every card on the account", "This stays off unless two of this customer's own cards are confirmed. There is no field for a stolen password, so we do not invent one."],
];

function ExampleCurve() {
  const steps = [
    { name: "The bank's own score", p: 0.39 },
    { name: "A phone we have not seen", p: 0.56 },
    { name: "That phone was in an older fraud case", p: 0.83 },
    { name: "The card has been quiet for a long time", p: 0.76 },
  ];
  const width = 560;
  const height = 150;
  const padX = 28;
  const padY = 16;
  const points = steps.map((step, index) => {
    const x = padX + (index / (steps.length - 1)) * (width - padX * 2);
    const y = height - padY - step.p * (height - padY * 2);
    return { ...step, x, y };
  });
  const line = points.map((point, index) => `${index ? "L" : "M"}${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");
  const mid = height - padY - 0.7 * (height - padY * 2);
  return (
    <figure className="curve">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="Example of how the chance moves">
        <line className="guide" x1={padX} y1={mid} x2={width - padX} y2={mid} />
        <path d={line} />
        {points.map((point) => (
          <circle key={point.name} cx={point.x} cy={point.y} r="4" />
        ))}
      </svg>
      <ol>
        {steps.map((step) => (
          <li key={step.name}>
            <span>{step.name}</span>
            <span>{Math.round(step.p * 100)}%</span>
          </li>
        ))}
      </ol>
    </figure>
  );
}

export function Guide({ onBack }: { onBack: () => void }) {
  return (
    <main className="board guide">
      <header className="board-top">
        <div>
          <button type="button" className="text-btn" onClick={onBack}>
            Back
          </button>
          <h1>How this works</h1>
          <p>The case page stays short. This page is what each part means.</p>
        </div>
      </header>

      <section className="guide-block">
        <h2>How one case moves</h2>
        <ol className="flow">
          {STEPS.map(([title, detail]) => (
            <li key={title}>
              <strong>{title}</strong>
              <span>{detail}</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="guide-block">
        <h2>Who is allowed to decide</h2>
        <div className="roles">
          <article>
            <h3>The rules</h3>
            <p>They pick the actions. They run twice: before any customer answer, and after. A writing model cannot add an action.</p>
          </article>
          <article>
            <h3>Jev</h3>
            <p>We use Jev, version jev-1.13-free, for three checks only. It does not pick the actions, and it does not write the paragraph.</p>
          </article>
          <article>
            <h3>The note</h3>
            <p>One writer turns the facts into a short paragraph, and into the bank report when the rules already asked for one. It does not change the chance or the actions.</p>
          </article>
          <article>
            <h3>The graph</h3>
            <p>Charges, cards, phones, older cases, and the policy notes live there. The case is saved there and read back. It counts only when the two copies match.</p>
          </article>
        </div>
      </section>

      <section className="guide-block">
        <h2>Jev</h2>
        <p className="lead">
          Jev is the model we call on every case. It is pinned to jev-1.13-free. We give it a short list of choices. It answers with a chance for each choice, not a paragraph.
        </p>
        <ol className="rulebook">
          <li>
            <span>1</span>
            <div>
              <strong>What kind of fraud is this?</strong>
              <p>Asked only when a fixed check has not already named the shape. If Jev’s top two answers are too close, we do not force a name.</p>
            </div>
          </li>
          <li>
            <span>2</span>
            <div>
              <strong>Is one more lookup worth it?</strong>
              <p>The choices are the other cards on this phone, the wider group of cards, older cases, the policy note, or none. One lookup at most.</p>
            </div>
          </li>
          <li>
            <span>3</span>
            <div>
              <strong>Does this sentence stick to a fact we already have?</strong>
              <p>After the paragraph is written, Jev keeps a sentence that quotes a fact and drops one that adds something new.</p>
            </div>
          </li>
        </ol>
        <p className="fine">If Jev does not answer, the case records that and uses a backup: no forced pattern name, no extra lookup unless the phone is already shared, and only sentences that quote a fact. The backup does not block a card. The rules still pick the actions.</p>
      </section>

      <section className="guide-block">
        <h2>What the percent means</h2>
        <p className="lead">
          The percent is how strongly the facts lean toward fraud. It starts from the bank's own score. Each new fact moves it up or down. The dashed line is 70%. Under that line, one weak sign is not enough to block a card.
        </p>
        <ExampleCurve />
        <p className="fine">This drawing is an example, not a live case. A worrying fact lifts the line. A reassuring fact brings it down. We are not sure until the facts settle on one side.</p>
      </section>

      <section className="guide-block">
        <h2>The ten rules</h2>
        <p className="lead">Every case is checked against all ten. A rule that does not apply is still recorded, with the reason.</p>
        <ol className="rulebook">
          {RULES.map(([id, when, then]) => (
            <li key={id}>
              <span>{id}</span>
              <div>
                <strong>{when}</strong>
                <p>{then}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="guide-block">
        <h2>Other answers</h2>
        <p className="lead">
          If the customer is asked, we assume one answer and that becomes the plan we use. The other answers are kept so you can see what would have changed. They are not what happened. A yes can close a case. A no can add a block. No answer means we watch the card.
        </p>
      </section>

      <section className="guide-block">
        <h2>The report on a case</h2>
        <p className="lead">
          On the case page, the report is the customer's own words and the purchase they asked about. It is not a technical write-up. A bank report, when the rules ask for one, stays inside the bank. This screen does not text the customer, freeze a card, or send a refund.
        </p>
      </section>
    </main>
  );
}

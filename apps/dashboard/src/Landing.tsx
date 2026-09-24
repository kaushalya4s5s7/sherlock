const openings = [
  {
    id: "HHG-003",
    title: "The customer says they did not make it",
    text: "A dispute opens the case. The desk still checks whether the charge repeats before anyone blocks the card.",
  },
  {
    id: "HHG-019",
    title: "A high score on a monthly charge",
    text: "The bank score is the reason to look. A repeating amount is a reason not to block.",
  },
  {
    id: "HHG-008",
    title: "No reply, so the action changes",
    text: "The desk asks once. When nothing comes back, the recommendation changes and waits for a person.",
  },
  {
    id: "HHG-014",
    title: "A device the policy never named",
    text: "One more lookup across the shared phone. The pattern stays undocumented. The report waits for approval.",
  },
];

export function Landing({ onOpen }: { onOpen: (id: string) => void }) {
  return (
    <main className="landing">
      <header className="landing-bar">
        <span>Case desk</span>
        <span>Twenty alerts, November and December</span>
      </header>
      <section className="landing-copy">
        <h1>Open the alert. Read the card. Sign the action.</h1>
        <p>
          The bank already scored the purchase. That score starts the investigation. The desk reads the graph,
          writes what it found, and stops when the evidence is enough to defend the next action. A block, a decline,
          or a report does not go out until you approve it.
        </p>
      </section>
      <ol className="openings">
        {openings.map((item) => (
          <li key={item.id}>
            <button type="button" onClick={() => onOpen(item.id)}>
              <strong>
                {item.id} {item.title}
              </strong>
              <span>{item.text}</span>
            </button>
          </li>
        ))}
      </ol>
      <p className="landing-foot">
        <button type="button" className="text-button" onClick={() => onOpen("list")}>
          Open the full case list
        </button>
      </p>
    </main>
  );
}

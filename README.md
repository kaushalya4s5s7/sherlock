# Jev × TigerGraph: a fraud investigation agent

An alert arrives with no fraud flag on the transaction. This agent opens that one case, reads the card from TigerGraph, and recommends the next action. A block, a decline, or a report waits for a person.

## What is the problem?

A fraud analyst has to stitch the story by hand. The charge is in one table. The phone is in another. Older cases are in a third. The policy is a document. By the time those pieces are together, the money may already be gone.

The hard part is the middle. Some alerts are clearly bad. Some are the customer's own purchase. Many are mixed: a new phone, and also a long quiet history. The agent has to say what it knows, what it still does not know, and what to do next.

## What did we build?

One investigation, from the alert to a case a person can sign.

- TigerGraph holds the transactions, the devices, the older cases, the policy notes, and the finished exam cases.
- Jev (`jev-1.13-free`) is allowed three gates. It does not pick the action.
- A fixed rule book, R1 through R10, writes the action list. It runs twice: before any customer answer, and after one assumed answer.
- Gemini writes the summary, and the report text when a report is already in the plan.
- LangGraph checkpoints each step, so a crash does not ask twice.
- A desk shows the chance, the pattern, the graph neighborhood, the rules, and the signature.

Twenty benchmark alerts, HHG-001 through HHG-020, each become an answer file and an `ExamCase` vertex. The vertex counts only after a read-back returns the same verdict and the same money.

## Why TigerGraph, and not a normal database?

A normal database can store every row. The investigation asks a different question: who is connected to this charge?

"Which other cards used this phone, and did any of them appear in a confirmed case?" In tables, that is a chain of joins, and it gets slower and easier to get wrong as the path gets longer. In TigerGraph it is a walk. The charge sits on a card (`TXN_ON_CARD`). The charge came from a phone (`FROM_DEVICE`). Older cases sit on cards (`CASE_ON_CARD`). One installed query follows that path and returns the neighbors.

That is the difference we use:

| Question | Tables | TigerGraph |
| --- | --- | --- |
| What else touched this phone? | Join transactions to devices to cards | Walk `FROM_DEVICE`, then back to the other cards |
| Have we seen this shape before? | Search a case log by columns | Walk from this card, or this phone, to `ClosedCase` |
| Which policy paragraph applies? | Paste a long document into the prompt | `vectorSearch` on `PolicyNote.vec` returns one note |
| Can the next case use this one? | Hope someone queries the log | The finished case is a vertex, `EXAM-HHG-…`, linked to the card, the phone, and the purchases |

The agent never writes GSQL at runtime. Official TigerGraph MCP exposes one tool, `run_installed_query`. The same pack runs on every case: the charge, the card history, the phone and who else used it, the region, a repeating amount, older cases, and the money in the episode. Jev may then spend one more query: the other cards, a short shared-device walk, older cases again, the closest policy note, or nothing.

The policy note is the GraphRAG step. The graph supplies the structure. The vector index supplies one paragraph. Gemini sees that paragraph beside the claims. It does not see 590,000 rows.

## Why Jev?

The graph already knows the facts. The rules already know the actions. What is left are three choices that are not a formula.

1. If the fixed pattern checks did not lock a name, which shape is this? Jev returns a chance for each shape. If the top two are too close, the name stays blank.
2. Is one more lookup worth it, and which one?
3. After the paragraph is written, does each sentence quote a fact we already have? A sentence that adds a fact is dropped.

Jev answers with a probability map, not a paragraph, and not an action. If Jev does not answer, the miss is recorded. The rules still decide.

## Which agent framework did we use?

LangGraph. It is the harness around the engines, not the brain.

It runs the steps in order and saves a checkpoint after each one. If the process dies, it resumes from the last checkpoint. It will not send a second customer question, and it will not walk the graph a second time. It does not choose the pattern, the chance, or the action.

The engines stay separate on purpose:

| Engine | Job |
| --- | --- |
| Intake | Open one row: a customer dispute, a bank score, or an analyst request |
| Graph | Read TigerGraph through installed queries |
| Belief | Start from the bank score. Each fact adds a frozen log-odds weight. The chance is the sigmoid of that total |
| Pattern | Check the five named shapes, plus the unnamed bucket. Lock a name when the measurements match |
| Control | Jev's three gates |
| Policy | R1–R10, twice |
| Reply | Assume one customer answer from the facts. The language model does not invent it |
| Stop | Name the fact the decision rests on. Drop that family and the actions change |
| Language | Gemini rewrites claims we already have |
| Memory | Upsert `ExamCase`, then read it back |

## How does one case walk through?

**What opens it?** A customer says the charge is not theirs, the bank score is high, or an analyst asks. There is no fraud label on the row. No model has been called yet.

**Where do the facts come from?** TigerGraph, through the pack above. An empty neighbor list is a real finding: no other card on this phone. It is stored as evidence.

**How does a fact become a chance?** The bank score is the prior. A new phone pushes the chance up. A phone tied to an older confirmed fraud pushes it further. A long quiet history, a trip, or a monthly charge pulls it down. Older cases guide the search. They are not proof of this charge.

**How do we name the shape?** Fixed checks look for tiny test charges, a stolen online purchase, an online purchase from a new phone, a purchase far from home, someone else on the account, and a shape the bank never named. If a check locks a name, Jev is not asked to rename it.

**When do we look again?** Once, if Jev allows it. Then the walk stops.

**Who picks the action?** The rules. Pass 1 has no customer answer. If the plan still needs the customer, we assume one answer from the facts and the rules run again. Both lists stay on the case. The answers we did not assume stay too, marked as not what happened.

**When is it fraud, a real purchase, or still uncertain?** Three questions, in order. Did the rules close it as a real purchase? Is the shape one the bank never named? Is the chance high enough to call fraud? If none of those fire, the case stays uncertain and the card stays open. A named pattern does not skip those questions.

**Who explains it?** Gemini, from the claims already on the case. Jev then checks each sentence.

**Who is allowed to act?** Open a case, watch a card, warn, or close a real purchase can proceed on their own. A block, a decline, or a report waits for a signature. Signing an action that is not on the final list is refused. We do not text a real customer or freeze a real card. The case file is that record.

**How does the next case remember this one?** The verdict and the money are written to `EXAM-<case id>` and tied to the card, the other cards, the purchases, and the phone. We read the vertex back. It counts only when the two copies match. Later alerts can retrieve it the same way they retrieve older closed cases.

## How do you run the desk?

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
PYTHONPATH=packages/graph .venv/bin/python -m graph.private.local_index
PYTHONPATH=packages/contracts:packages/intake:packages/graph:packages/belief:packages/pattern:packages/control:packages/policy:packages/reply:packages/stop:packages/language:packages/memory:packages/answer:packages/harness:apps/api .venv/bin/uvicorn api.main:app --port 8787
```

In another terminal:

```bash
cd apps/dashboard && pnpm install && pnpm dev
```

Open http://localhost:5173. Pick a finished case. The screen is the investigation. The API does not compute a rule.

# Read me first

You are a junior. This is the whole project in normal words. The strict version is `ARCHITECTURE.md`. If these two ever fight, the architecture file wins.

## What are we even building?

A helper for a fraud analyst.

Someone at the bank flags a card charge. Our program looks at the graph, old cases, and the bank's rules, then writes a case file that says:

- is this fraud, legit, or "I don't know yet"
- what kind of fraud
- what the bank should do **before** asking the customer
- what it should do **after** the answer
- who has to approve that (the bot, a team lead, or a manager)
- a government report, only when the rules say so

We do this for 20 cases: `HHG-001` to `HHG-020`. Each one becomes `cases/HHG-00X.json`. We also save the case inside TigerGraph.

The chatty AI does not decide. It writes the paragraph at the end.

## Why not just ask ChatGPT "is this fraud"?

Because the score lies, and the model will sound sure anyway.

The bank already put a risk score on every transaction. A lot of high scores are normal people. Some real fraud scores almost zero. About half of our 20 exam cases are legitimate. An agent that blocks everybody fails.

Also the grader wants a file with exact field names, exact action names, and real ids from the dataset. A nice paragraph with made-up ids scores zero.

## The one picture

```text
alert comes in
    → look up the graph (same checks every time)
    → turn those facts into a probability
    → rules pick the actions
    → maybe ask the customer (we fake the reply, and we say so)
    → rules pick the actions again
    → stop
    → AI writes the summary from the facts only
    → save the case in the graph
    → write the JSON file
```

That is the whole agent. Everything else is a detail of one of those lines.

## Who does which job?

Think of a small team. Nobody does two jobs.

| Person | Job | What they must not do |
| --- | --- | --- |
| TigerGraph | Count stuff. Other cards on this phone. Tiny charges in a row. Old cases. | Decide to block someone |
| Belief code | Turn those counts into a probability from 0 to 1 | Invent a story |
| Rules code (R1–R10) | Pick the actions and who approves them | Ask a model what feels right |
| Jev | Three small calls: do we need one more graph lookup, is this a pattern the bank never named, does this sentence match the evidence | Block a card. Write the report |
| Big language model | Write the short summary and the report | Change the probability, the ids, or the actions |
| Reply faker | Guess what the customer would say, using a fixed rule | Be creative |
| LangGraph | Remember the step we were on, so a crash does not start over | Think |

Jev is a model that only answers yes/no and multiple choice, with a probability. It is fast and it cannot ramble. We use it as the shift lead for those three questions. The rule book still signs the action.

## Why those graph checks run every time

If we let the AI choose what to look up first, it can forget the one check that matters.

Every case, we always ask the graph:

1. What is this transaction, this card, this customer?
2. What did this card do just before and after? (tiny test charges, or four buys just under $500)
3. What phone or browser was it, and is that device new?
4. Did other cards use that same device?
5. Has this card ever paid in this region before?
6. Is this amount a monthly repeat?
7. Any old closed case on this card or this device?

After that, Jev may say "go look at the whole device group" or "you already have enough, stop." It does not get to skip step 2.

Heavy stuff (grouping all cards in the database into communities) is done once, overnight, and saved on the card. We do not rerun it while a case is open. 590,000 transactions is a lot.

## How the probability works, without the math lecture

Old cases are the only place anyone wrote down the truth. July to September we learn:

- when the bank score was in some range, how often was it actually fraud
- when we saw "new phone" or "shared device", how much more often that showed up in real fraud than in cleared cases

That becomes the starting probability. Each new fact nudges it up or down.

October is the practice test. We check if our probabilities were honest. Then we freeze the numbers. We do not peek at the 20 exam cases to "fix" the score. The grader scores honesty. A fake 0.99 on everything looks dumb.

An old case can tell us "last time this phone was fraud, look there again." It is not proof that **this** charge is fraud.

## The rules, in junior words

The bank wrote 10 rules. Our code follows them in this order. Learn these. They are the exam.

**R7 first, if the customer complains and the charge repeats every month.** Open a case, ask them, warn them. Do not block. It is probably Netflix and they forgot.

**R5, card testing.** Three or more tiny online charges (under $5) within an hour, then a bigger buy. Decline it and ask for a code. If a buy over $100 already went through, block the card.

**R9, weird pattern we cannot name.** The history file already has two of these: one Samsung model on a hidden proxy used by lots of people, and four purchases in 40 minutes each just under $500. Say `undocumented`, describe it in your own words, open a case, file a report, call an analyst. Do not pretend it is a normal stolen-card pattern.

**R6, same phone or same area on several cards that actually look like fraud.** Case, report, watch the other cards. "Same phone" by itself is only a clue. The other cards have to look dirty too.

**R1, one weak clue and probability under 0.70.** Ask the customer or send a code **before** you block. A high bank score by itself is this situation. This is how all 900 cleared cases were handled.

**R10.** Do not block every card the customer owns unless two of their cards are actually confirmed, or we know their login was stolen. We do not have a "password stolen" column. Leave this action off unless two of their cards are in the mess.

**Open a case** when probability is at least 0.30, or we are about to ask someone, or the customer already complained.

**File the government report** only when we really think it is fraud **and** one of these is true: more than $1,000, shared device or region tied to other fraud, or the weird unnamed pattern. Most real fraud in the history file did **not** get a report. 4,268 confirmed cases were just "open case + block card."

Who approves:

- the bot can ask, warn, watch, open the case, close as legit, escalate
- a team lead must approve a decline, and a block when the money is $2,500 or less
- a manager must approve a big block, blocking all cards, and every report

We recommend the lead/manager actions. We do not pretend we already did them.

## Why we fake the customer, and how we do it honestly

The dataset does not include replies. The README says: pretend, and write down what you assumed.

If the AI invents the reply, it will say "customer denies" every time and then block everyone. That fails, because half the cases are fine.

So the reply is a boring if-statement:

| What we already saw | What we assume they say |
| --- | --- |
| Same amount every month | They don't recognize the name, but it matches their monthly charge. Still no block |
| They normally shop in this region, or it looks like a trip | They confirm it |
| New phone, no proxy, no other cards, normal amounts | They confirm the new phone |
| Test charges, the under-$500 trick, or a proxy phone tied to old fraud | They deny it |
| Still messy, probability in the middle | They never reply. We watch the card and maybe call an analyst |

If we are already very sure (probability ≥ 0.85 or ≤ 0.15) **and** we have two different kinds of facts, we do not ask. Asking again wastes the case.

The customer's first message "I never made this" is the **alert**, not the answer to our question. Lots of people say that about a subscription. We still check R7 before we block.

## When we stop

Stop when:

- probability is very high or very low, and we have two **different** kinds of facts (not the same query twice), or
- the fake reply settled it, or
- another question would not change the action

Write that reason in `stop_reason`. Stopping too early and rambling forever both lose points.

## What the output file is

One JSON per case. Three chunks:

1. **case** — the internal notes. Verdict, probability, pattern, list of evidence, money at risk, old case ids, and whether we saved it in the graph.
2. **sar** — the report. If we are not filing, this is empty on purpose.
3. **next_best_actions** — the list before the reply, the list after, and one sentence on what changed. If we never asked, the two lists match and the sentence is `nothing`.

Every id in that file has to exist in the CSVs. The sample JSON in the README is a shape example. Its transaction ids are fake. Do not copy them into HHG-017.

`written_to_graph: true` only after we read the case back out of TigerGraph and it matches. Writing it in a Python dict does not count.

## What you build, in order

Do not start with the UI.

1. The rules function, with tests. Fake some facts, check the actions. No database yet.
2. Load the graph. Run the checks by hand on one old fraud case and one old cleared case.
3. Learn the probability tables on July–September. Look at October. Freeze them.
4. Hook up "actions, then maybe a reply, then actions again." Produce one JSON. Run the schema test.
5. Save that case in TigerGraph and read it back.
6. Run all 20, in order, so a later case can see an earlier one.
7. Then the screen: timeline, probability, actions before, actions after, report if any.
8. Film four cases: a high score that is actually fine, a monthly charge we do not block, a case that changes after the reply, and HHG-014 (the analyst asking about a weird device).

## Words you will see, translated

| Word | Means |
| --- | --- |
| Trigger | Why we woke up: high score, customer complaint, or an analyst asked |
| Pattern | The type: card testing, online fraud, new device, wrong region, account takeover, something unnamed, or none |
| Exposure | Dollars in the bad episode. If it is legit, this is 0 |
| Case | Our internal file. Not the government report |
| SAR / FILE_REPORT | The report that leaves the bank |
| Route `auto` / `L1` / `L2` | Bot / team lead / manager |
| Ledger | The list of facts we actually found, each with an id |
| GraphRAG | Give the writer the graph facts plus the policy paragraph, not the whole database |
| MCP | The plug that lets our code call TigerGraph as tools |
| Jev | The yes/no model. Not the writer |

## Stuff that will get you in trouble

- Treating the risk score as the answer
- Blocking because the customer complained, before checking if it is a monthly charge
- Filing a report on every fraud
- Letting the language model pick `BLOCK_CARD`
- Making up transaction ids
- Tuning the model on the 20 exam cases
- Looking up the public Kaggle fraud labels. That is disqualification. The ids here were changed on purpose
- Saying the case is in the graph when you only saved a JSON file

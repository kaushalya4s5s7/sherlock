# How to build the HHGOA fraud investigation agent

A first-principles guide, then the current standard.

Read this before writing code. The hackathon is due **24 September 2026, 11:59 PM IST**. The product judges score is a **defensible case**, not a chatbot that “sounds like an investigator.”

This note is research, not the official spec. Policy rule numbers, approval tiers, and the answer JSON shape below come from public HHGOA 2026 write-ups that quote `dataset/HHGOA_IEEE/README.md`. **Open that README first and treat it as the only source of truth.** If a write-up and the README disagree, follow the README.

---

## 0. What you are actually building

Fraud teams already have a risk score. The score is a trigger. It is not a verdict. The dataset has about 590,000 card transactions, about 13,500 customers, device records, and a bank model score on every transaction. There is **no `is_fraud` column**. Closed investigations from the first four months are the memory. Twenty cases from the last two months (`HHG-001` … `HHG-020`) are the blind exam. Every team is scored on the same twenty.

The agent’s job, in order:

1. Start from a trigger: risk score, customer report, or analyst request.
2. Open or continue a **case**.
3. Gather evidence from the graph, history, devices, identity, prior cases, and policy documents.
4. Name the likely fraud pattern and say how sure you are.
5. If you are not sure enough to act, request **one** policy-approved piece of extra evidence.
6. Recommend the next actions **twice**: once before that extra evidence, once after it arrives.
7. Explain which evidence was used, what is still uncertain, and why those actions follow.
8. Write the case, the decisions, and the outcome back into the graph so the next case can use them.

Actions such as freezing a card, messaging a customer, or filing a report may be mock APIs. The **record** of the recommendation, the approval route, and the before/after change must be real.

Judging, in the order that should drive the design:

| Weight | Criterion | What actually wins |
| --- | --- | --- |
| 25% | Investigation accuracy | The right pattern, backed by graph evidence, including patterns the policy document does not name |
| 25% | Next best action | Knowing when **not** to block, asking for the evidence that would change the action, then updating the action |
| 15% | Agentic design | A real state machine, tools, memory, and permissions — a loop with a stop condition |
| 15% | Innovation | Graph + GraphRAG + uncertainty, used for a decision a vector search cannot make |
| 10% | Case summary | A case a compliance officer could defend |
| 10% | Demo | The same flow, visible, on a real benchmark case |

---

## 1. First principles

### 1.1 An agent is a loop with a stop, not a smarter prompt

A language model answers one question. An agent is that model plus:

- a **goal** (produce a defensible action for this case),
- **tools** that change what it knows,
- **state** that survives each step,
- a **policy** for what it is allowed to do,
- a **stopping rule**.

Without the stopping rule it is a runaway loop. Without the policy it is an intern with the power to block cards. Without state it re-investigates the same transaction every turn and forgets what the customer said.

Anthropic’s engineering note [Building effective agents](https://www.anthropic.com/engineering/building-effective-agents) draws the line that matters here. When the steps are known in advance, build a **workflow**: fixed nodes, a router, maybe one loop. Use a free-roaming agent only for the step whose next move depends on what the last tool returned. This hackathon’s flow is already written down (trigger → investigate → evidence → uncertainty → maybe more evidence → action → explain → memory). That is a workflow with **one** decision loop inside it: “do I have enough to act?”

### 1.2 Three different jobs are hiding inside “the agent”

Almost every weak fraud agent fails because one model is asked to do all three:

| Job | What it is | Who should own it |
| --- | --- | --- |
| **Control** | Which step next. Is evidence enough. Which action class is legal. | A typed decision, then a deterministic policy |
| **Evidence** | Who shares this device. What happened in the last hour. Which old cases look like this. | TigerGraph. Installed GSQL. Never the LLM |
| **Language** | The case narrative, the SAR prose, the explanation of why | A strong LLM, allowed to write only from the evidence packet |

The [REFLEX paper](https://arxiv.org/abs/2609.26532) (September 2026) states the same split for agents in general: control, argument filling, and free-form generation are different computations. Mixing them is why agents feel magical in a demo and indefensible in a fraud case.

### 1.3 Fraud investigation is a process, not a classifier

Public HHGOA write-up [Tark](https://dev.to/mukull-s/a-fraud-investigation-agent-247l) puts the lesson cleanly: a high fraud probability does not mean “block the card.” The action depends on the evidence, how much of the checklist you have, how uncertain you still are, the bank’s rules, and whether a human must approve.

Two consequences:

- The bank risk score is a **prior**, not the answer. Public teams report cases where a high score is a customer at home, and a very low score sits on a multi-account device ring. The graph is what separates those.
- A past case can tell you **what to look for**. It is not evidence that **this** transaction is fraud. Keep those two uses in different fields of the case record.

### 1.4 Who owns the state

Design this before any framework.

```
Trigger
  → Case record (the source of truth for THIS investigation)
       → Graph queries (facts; TigerGraph owns entity truth)
       → Document retrieval (policy, typology, regulation text)
       → Uncertainty score (how sure, and what is missing)
       → Policy engine (the only component allowed to name an action)
       → Approval route (auto / human)
       → Explanation (LLM, read-only over the case)
       → Write-back (case vertex + edges in the graph)
```

| State | Owner | Lifetime | What breaks if you put it somewhere else |
| --- | --- | --- | --- |
| Customers, cards, transactions, devices, edges | TigerGraph | Permanent | The LLM will invent neighbors |
| This investigation: evidence, findings, decisions, NBA before, NBA after | Case record, also written to the graph | For the life of the case | You cannot show progression, and you fail the submission format |
| “Have I already asked the customer?” | Case record | This run | The agent asks twice or skips the before/after NBA |
| What actions are legal | Policy engine, code, versioned | Changes only when policy version changes | A prompt change silently changes who gets blocked |
| Similar old cases | Graph (+ a small text index) | Permanent, updated when cases close | Memory either never helps, or it contaminates the current probability |
| Prose | Generated at the end from the case | Disposable | If prose is the source of truth, you cannot audit or replay |

**Control plane** is the state machine, the policy, and the approval. **Data plane** is GSQL over 590k transactions. Do not pull raw transaction tables into the model. Pull a small, typed evidence packet.

### 1.5 What “done” means

An investigation is done when a **named rule** says one of these is true:

- enough evidence exists for a reversible action (monitor, warn, verify), or
- enough evidence exists for an irreversible action **and** the approval route is recorded, or
- the single allowed evidence request has been answered (confirm, deny, or no reply), or
- a hard stop fires (max steps, conflicting signals that only a human can resolve).

“The model feels confident” is not a stopping rule. LLM verbal confidence clusters near 90–100% even when accuracy is much lower. That finding is why calibrated decision models showed up in 2026 (see §4).

### 1.6 What failure looks like, so you can design for it

| Failure | What the system must do |
| --- | --- |
| TigerGraph is down | Same query interface against a local graph that implements the same contracts. The case record does not change shape |
| A tool returns empty or errors | Record the miss as evidence (“shared-device query returned 0”). Do not let the model treat silence as “no fraud” or as “fraud” |
| The model loops | Max steps. Each tool is idempotent. The same query with the same arguments is cached on the case |
| The customer never replies | Policy has an explicit no-reply branch. Time is simulated in the benchmark |
| The process crashes mid-case | Checkpoint the case after every node. Resume from the last committed node. Do not re-block a card because you restarted |
| The model wants to block everyone | The tool that blocks is not callable by the model. The policy engine emits the action. A permission check rejects anything the current role cannot execute |

---

## 2. Where agents are weak today

These are the failure modes that show up in production write-ups and in the 2025–2026 papers. They are also exactly the ways a fraud demo dies in judging.

### 2.1 One model, every decision

The default “ReAct agent + 40 tools” picks a tool, writes arguments, decides policy, and writes the SAR in the same context. Errors compound. By the time it writes the narrative, the narrative is arguing for whatever tool it happened to call.

Anthropic’s multi-agent research write-up and their tools guide say the same thing from the other side: agents fail on vague tools, redundant calls, premature “done,” and lost context. They spent more time fixing **tool contracts** than prompts. A tool that demands an absolute id beats a tool that says “look around.”

### 2.2 Tool choice is easy. “Should I act?” is hard

REFLEX measured this directly on Berkeley Function Calling:

- Picking **which** function: about **98.4%**.
- Deciding **whether any function should be called**: about **52%**.

Wrong calls still carried a mean confidence of about **0.78**, so a naive “if confidence > 0.7, do it” gate still executes mistakes.

For this hackathon that gap is the product. “Block card” and “ask the customer” are near-valid alternatives. They differ by one policy fact (did the customer deny it? is the signal weak? is exposure high?). REFLEX’s controlled experiment showed that swapping a near-valid alternative from “go read more” to “commit an irreversible write” **does not change accuracy much** and **does change how often the model commits irreversible actions**. Accuracy of the label and safety of the action are different numbers. Report both. Optimize the second with code, not with a prompt.

### 2.3 Bigger action menus make control worse

In REFLEX’s factorial, growing the action set from 10 to 50 choices dropped accuracy about 7 points, and the damage sat in **authorization** decisions, not in ordinary retrieval. A fraud agent with `block`, `block_all`, `decline`, `monitor`, `warn`, `verify`, `step_up`, `file_sar`, `escalate`, `close`, `allow` is already in that danger zone if the model chooses among them freely.

Shrink what the model is allowed to choose. Let it choose **which evidence to fetch** from a short list. Let policy choose the action.

### 2.4 Confidence is a costume

Generative models are trained to sound sure. A 2025 judge study (cited in the Arize write-up of Jev) found judges piling predictions at 90–100% confidence while landing well below that in accuracy. If your uncertainty gate is “the model said 0.9,” you will block innocent customers and also miss the case where you should have asked one question.

### 2.5 Vector RAG cannot see a fraud ring

Embedding search finds documents that share words. It does not find “this device was used by 50 other cards.” That path is a graph traversal. Public GraphRAG-vs-plain-RAG comparisons on this same dataset describe plain RAG as blind to device sharing, velocity, and card-to-card links. Use vectors for **text**: policy clauses, typology write-ups, analyst notes. Use the graph for **structure**.

### 2.6 Memory that cheats

If you embed old case summaries and then let them move today’s fraud probability, a lookalike cleared case and a lookalike confirmed case both “feel relevant,” and the model averages them into a story. Memory should answer: “cases with this shape were fraud 80% of the time, and the analysts checked device sharing first.” The probability for **this** card still moves only when **this** case’s evidence ledger gains an item.

### 2.7 Free-form query generation

TigerGraph MCP can generate GSQL from English. That tool is useful while you are developing queries. It is a bad tool to leave in the agent’s hands during a scored run. Generated queries hallucinate edge names, scan too wide, and are not reproducible. Install the queries. Give the agent typed parameters (`card_id`, `window_minutes`).

### 2.8 No case, no progression

A single final JSON that says “fraud, block card” fails the brief even if the label is right. Judges want the internal record: evidence added over time, the action **before** the extra evidence, the action **after**, what changed, and who must approve.

### 2.9 Agents mark themselves complete

Anthropic’s long-running-agent harness note: models declare success after a local check and skip the end-to-end condition. Your sufficiency node must be a function over the evidence ledger and the policy, not a sentence the model emits.

---

## 3. Where agents got better, and the standard to copy

The useful 2024–2026 progress is not “a bigger model.” It is a handful of constraints that make the loop inspectable.

### 3.1 Workflow first, freedom only where the path branches

Anthropic’s patterns, in the order you should consider them:

1. One well-built prompt with the evidence already retrieved. Often enough for the **explanation**.
2. Prompt chain. Fixed steps. This is most of the investigation.
3. Router. Send a customer-dispute trigger down a different first step than a risk-score trigger.
4. Parallel gather. Device ring, velocity, history, and similar cases can run together.
5. Evaluator-optimizer loop. **One** loop: uncertainty → request evidence → reassess. Cap the iterations.
6. Free agent. You do not need this for the exam. The twenty cases fit a state machine.

LangGraph is the boring, correct runtime for (2)–(5): nodes, a typed state object, checkpoints, and a human interrupt on the approval edge. Crew-style “five analysts talking” adds latency and disagreement you then have to adjudicate. Skip it unless a node is genuinely a different skill with a different context.

### 3.2 Tools as narrow contracts

From Anthropic’s tool-writing guidance, applied here:

- Few tools. Each name is a task a fraud analyst would recognize: `card_history`, `shared_devices`, `velocity`, `similar_cases`, `policy_passages`.
- Return a small structured payload plus a one-line claim, a source id, and the entity ids. Cap list lengths.
- Errors must say what was wrong and what argument would be valid.
- Absolute ids only (`TransactionID`, `card_id`). No “the last transaction.”
- Log every call. Redundant calls mean the tool is too small or the description is vague.

TigerGraph’s MCP server exposes schema inspection, raw GSQL, installed queries, and optional NL-to-GSQL. Use MCP as the **adapter**. Expose to the agent only your installed investigation queries, not the raw GSQL console.

### 3.3 An evidence ledger, not a chat transcript

Every fact enters the case as an item:

```text
claim:        "Device D-1042 was used by 17 cards in 6 hours"
source:       graph | document | customer | analyst | external
ref:          installed_query shared_devices(card_id=...)
entity_ids:   [...]
observed_at:  step 3
supports:     shared_origin_ring
contradicts:  legitimate_recurring
```

The explanation node may quote these items. It may not create new ones. This is the difference between a case file and a completion.

### 3.4 Uncertainty as an explicit object

You need three numbers, kept separate:

| Number | Meaning | Moves when |
| --- | --- | --- |
| Fraud belief | How likely this activity is fraud | A new evidence item about **this** case |
| Coverage | How much of the checklist for the suspected pattern you have | You ran, or could not run, a required check |
| Decision readiness | Whether policy allows an action at this belief and coverage | Belief, coverage, contradictions, exposure, reply status |

A useful shape, used in public form by [CaseGuard](https://dev.to/kanha_9650/-caseguard-winning-with-uncertainty-gated-agentic-fraud-investigation-on-tigergraph-407p):

```text
readiness = w1*graph_support + w2*historical_rate + w3*signal_strength
            + w4*evidence_coverage - contradiction_penalty
```

Weights are a hypothesis. Fit them on the **closed** cases (the first four months), never on the twenty exam cases. The historical term is a prior. The contradiction penalty is how you avoid blocking a customer who looks like previously cleared travel or a subscription.

### 3.5 Ask for the evidence that would change the action

[Tark](https://dev.to/mukull-s/a-fraud-investigation-agent-247l) uses an evidence compass: expected value of information. In plain terms, for each legal question you could ask (customer confirm, step-up, analyst look at a device cluster):

```text
value(question) = how much the action would change if the answer is yes
                + how much it would change if the answer is no
                - cost(question)
```

Cost is policy cost, not dollars: bothering a customer, delaying a block while money moves, spending an analyst. If no question can change the action, stop and act. If one question can flip “monitor” to “block” or “close,” ask that one, log the NBA **before** you ask, then log the NBA **after** the answer.

That before/after pair is 25% of the score. Build the state fields on day one: `nba_initial`, `nba_after_evidence`, `what_changed`.

### 3.6 Policy is code

The bank’s rules are a pure function:

```text
(evidence ledger, belief, coverage, exposure, customer_reply) -> ordered actions + approval tier
```

No LLM call inside that function. You can unit-test every rule. You can replay a case and get the same actions. The model’s only compliance job is to **cite** the rule id in the narrative.

Public write-ups of this dataset’s policy (verify against the README) describe rules in this spirit:

| Rule | Idea |
| --- | --- |
| Weak single signal | Verify with the customer or step-up **before** a block |
| Customer denies | Block the card, open a case; file a report only if exposure, shared devices, or a ring qualifies |
| Customer confirms | Close as not fraud |
| No reply | Monitor and decline pending auths; escalate if exposure is material |
| Card testing | Decline and step-up; if a larger purchase already cleared, block |
| Shared-origin ring | Case, report, monitor the connected cards |
| Disputed but looks like a subscription | Case and warn; do not block |
| Uncertain and material exposure, or signals conflict | Escalate to an analyst |
| Pattern the typology doc does not name | Case, report, escalate — do not force-fit a known label |
| Block every card of the customer | Only with a stated qualifier (multiple confirmed cards, or confirmed takeover) |

Approval tiers in those write-ups: **auto** for monitor, warn, verify, step-up, create case, close-as-clean; **L1** for decline and smaller blocks; **L2** for large blocks, block-all-cards, and filing a report. Read the README for the real thresholds and the real action names. Hard-coding a blog’s dollar amounts without checking the file is how you miss the exam.

### 3.7 GraphRAG means “retrieve the neighborhood, then the paragraph”

Pass the model a packet, not the database:

1. **Subgraph claims** from installed queries (devices, velocity, impossible travel, prior cases on this card).
2. **The one typology passage** that matches the leading hypothesis, plus the policy clauses the engine actually fired.
3. **Two or three closed cases** with the same structural signature, each with outcome and what the analyst did.
4. **What is missing** from the checklist.

That packet is the explanation’s only context. If a sentence in the SAR is not traceable to an item in the packet, delete the sentence.

### 3.8 Case memory is a vertex, not a chat summary

When a case closes, write:

- a `Case` vertex with pattern, outcome, exposure, actions taken, whether a report was filed, and the evidence checklist that mattered,
- edges to the cards, devices, and transactions involved,
- optionally an embedding of the analyst note for text search.

Next time, retrieve along structure first (“other cases touching this device or this email domain”), and use text similarity only to rank notes. Update memory when the human overrides the recommendation. The override is the label. The model’s first guess is not.

### 3.9 Stopping, permissions, replay

- Max evidence rounds: **one** customer/analyst ask in the scored flow, because the submission wants exactly the before and after.
- Irreversible tools check a capability token minted by the policy engine. The model cannot mint that token.
- Every run stores the tool trace. You should be able to rebuild the answer file from the trace with the model switched off.

---

## 4. Jev, and the research that says where to put it

### 4.1 What Jev is

**Jev** is TypeSafe AI’s first **System One** model, launched September 2026. Diogo Almeida (previously on the OpenAI RLHF work behind ChatGPT) is the public technical face. The name “System One” is the Kahneman split: fast, bounded judgments versus slow, generative reasoning.

What is public:

- It does **not** write paragraphs. It returns a **typed** answer: one label from a set you declare, plus a score and a probability.
- It produces that answer in **one pass**, not token by token.
- Training is described as **RLCD**, reinforcement learning for calibrated decisions: the objective is that when it says 80%, it is right about 80% of the time. The method, data, parameter count, and weights are **not** published. Treat calibration numbers from the vendor as claims until you measure them on **your** closed cases.
- You call `jev-latest` or a pinned version such as `jev-1.13.0`. Pin the version for the exam run.
- Community write-ups (Arize, September 2026) describe it as a judge/router: on a small set of decision workflows, roughly tied with a strong generative model on accuracy, much cheaper and faster, and actually emitting a probability. The interesting property is the probability, not the leaderboard.

Jev is the wrong model to write a SAR. It is a strong candidate for the judgments generative models fake.

### 4.2 The paper that matters: REFLEX

**REFLEX: efficient selective control in LLM agents**, Wu and Lim, NTU, [arXiv:2609.26532](https://arxiv.org/abs/2609.26532).

Architecture:

```text
state + allowed action set
        │
        ▼
   Jev  →  (choice, confidence)
        │
        ├─ confidence ≥ threshold and the choice is executable → do it
        └─ otherwise, or the step needs free text → strong LLM
```

What they found, and what you should believe:

| Result | Number | What it means for you |
| --- | --- | --- |
| Frozen 100-task sim, τ = 0.5 | 95% success vs 88% for the strong model alone, **72.7% fewer** strong-model calls | A typed gate can take the boring steps |
| Same autonomous subset across Qwen, Kimi, and DeepSeek | 66 of 100 tasks solved by Jev alone, all succeeding; failures were in the escalated remainder | The gate selects **tasks**, it does not imitate the big model |
| Which steps it replaces | Tool selection ~99%, “am I done?” ~77%, retrieval ~56%, **clarification ~28%** | It is good at routine control and weak at “do I need to ask?” |
| Action-set size 10 → 50 | about −7 points, concentrated on authorization | Do not hand Jev the full fraud action menu |
| Near-valid alternative swapped from read to irreversible write | Accuracy almost unchanged; irreversible mistakes and unnecessary deferrals **swap** | The dangerous fraud decision is exactly this shape |
| BFCL | 98.4% which-tool, **52%** whether-to-call; bad calls still ~0.78 confident | Thresholds do not make a relevance decision safe |
| τ²-bench style multi-turn | ~3.7× cheaper than strong-only; a **cheap LLM cascade was competitive** | If the only problem is routing easy tools, Jev is optional |

Their own conclusion: a decision layer earns its place when a large part of the trajectory is a **repeated bounded choice**, and when confidence separates safe autonomous steps from escalations. A fraud investigation is that trajectory. The authorization commit stays in policy, which is the bruise they measured, not a reason to leave Jev outside the loop. Section 4.5 is that split.

A hierarchical “pick a tool family, then a tool” ablation did **not** beat a flat choice once descriptions were fixed. Fewer menu items help. An extra routing stage introduces a new way to be wrong. Prefer a flat, short menu.

### 4.3 What changed in the last two weeks, in plain language

Think of a fraud analyst on a busy shift. She does not write an essay between every click. She looks at the screen and makes a fast call: same device as last week’s fraud, this charge looks like the Netflix one, I still need the customer to say yes or no, stop, I have enough. The essay comes at the end, for the file.

A normal LLM is the essay brain. It can do the fast calls, but it does them by writing, and then your code has to read the writing and hope it parsed. Jev is built to be the fast brain. You show it the case so far. You ask several yes/no questions, one multiple-choice question, and one rating, **in the same call**. It answers all of them at once, each with a probability, and it cannot return a sentence, a typo, or a label you did not list. TypeSafe shipped this in September 2026. LangChain wired it into the agent harness the same month. Four papers landed within days of each other. That speed is real. The way to use it is to let it **run the investigation**, not to ask it one extra classification at the end.

The three primitives, and why the difference matters:

| Primitive | What you get back | Use it when | Trap |
| --- | --- | --- | --- |
| **Noul** | A probability that a statement is true, from 0 to 1 | “Is the evidence enough?” “Are we looping?” “Would the customer’s answer change the action?” | A low number means “no,” not “maybe.” It can be low for every question at once. That is the point |
| **Choice** | One winner, probabilities that **sum to 1**, plus a confidence | “Which graph should I walk: device, time, email, or prior cases?” | It **always** picks a winner. If “none of these” is missing, a weird case gets forced onto the closest label, with a confident-looking score |
| **Score** | A point on an ordered scale, plus the distribution | “How strong is the match to this closed case?” “How covered is the checklist?” | Do not reuse a threshold you tuned on a Noul. TypeSafe’s own docs say the same question asked both ways can point opposite directions |

One call, many questions, one case state. That is why it can sit in the hot loop. A bolt-on is “after the agent finishes, ask Jev what the pattern was.” A spine is “every branch the investigator would make in her head is a question in that call, and the graph and the policy only move when the answers say so.”

### 4.4 The four papers, and the job each one gives Jev

**REFLEX** ([arXiv:2609.26532](https://arxiv.org/abs/2609.26532)) puts Jev on every step of an agent: which tool, whether to continue, whether this step is done. High confidence executes. Low confidence, or a step that needs sentences, goes to a strong model. It cut strong-model calls by about two-thirds on their sim. It also showed the bruise: Jev is excellent at “which lookup,” and weak when the choice is “am I allowed to commit.” Clarification was replaced only 28% of the time. So Jev runs the investigation steps. It does not become the person who blocks the card.

**Jev-Mem** ([arXiv:2609.23986](https://arxiv.org/abs/2609.23986)) is the one that matches this hackathon. Memory has a write path and a read path. On the write, Jev types the memory and decides which relations to draw (semantic, time, cause, entity). On the read, Jev picks which relation to walk, how much budget each relation gets, whether one more hop is worth it, and when to stop. The graph stores the facts. A normal LLM is called only to write the answer from what was retrieved. On their benchmark that controller was both more accurate than the best memory baseline (+11% relative) and much faster to build (6.6×). Their stop rule is exactly our uncertainty problem: stop when evidence is sufficient **and** nothing required is missing **and** contradictions are quiet, or when another hop is unlikely to help.

That is TigerGraph’s job description, with a brain. The other HHGOA teams walk a fixed set of queries every time. Jev-Mem says the walk itself is the agent.

**JEV-as-a-Judge** ([arXiv:2609.26550](https://arxiv.org/abs/2609.26550)), Carnegie Mellon, 21 September 2026. They compared Jev with sixteen judges, including GPT-6. On ordinary preference and on **factuality checked against supplied evidence**, Jev stayed within about three points of GPT-6, at a tiny fraction of the fee (their matched panel: about $0.04 per 1,000 judgments, median 0.15 seconds). On evidence-grounded HaluEval it was 87.5% against GPT-6’s 86.7%. The gap opens when the judgment needs a multi-step derivation, or when a fluent wrong answer is trying to fool it (JudgeBench 78.6% vs 93.1%). Their operating rule: **accept when the probability is high, escalate when it is low.** A frozen cascade kept 99% of GPT-6’s accuracy at 57% of the fee. For us that is the SAR gate. Every sentence has to be a claim about a ledger item. Jev judges “does this ledger item support this claim?” That is the workload it is good at. If confidence is low, the sentence does not ship, and a stronger model rewrites it or an analyst sees it.

**The smart if-statement** ([arXiv:2609.23886](https://arxiv.org/abs/2609.23886)) explains why this can live inside a loop at all. The answer is read off the model’s hidden state over the options you declared. There is no generated token, so there is nothing to parse and nothing malformed to handle. Many questions about one state cost one pass. An open 2B model in that family (decider-2b) answers in about 30 ms, which is database-lookup speed. Jev itself is hosted and closed. The paper even beats Jev on one recorded cohort and loses to hosted models on branch-shaped tasks. Read that as a warning, not as a reason to skip Jev: **measure it on our closed cases.** The architecture (typed head, one pass, N questions) is what we are copying. Hosted Jev is the engine we call. If the API is down, the same questions can be asked of a small open typed model. The questions do not change.

LangChain’s harness tutorial (September 2026) is the engineering version of REFLEX. Jev sits in middleware: before a tool runs, after a step, when checking “are we looping,” “did we finish,” “does this turn need a tool at all.” The last one must be a **Noul**. A Choice will always nominate a tool.

### 4.5 The investigation kernel: Jev in the middle, on purpose

Each cycle, the case ledger is the `state`. One Jev request asks the whole shift’s questions together.

**Nouls** — absolute, and allowed to all come back low:

- `evidence_sufficient` — enough to act under the current pattern
- `another_hop_useful` — one more graph query would change the picture
- `customer_reply_would_flip` — a yes or a no from the cardholder would change the action
- `signals_contradict` — the ledger contains a real conflict, not just two different facts
- `known_typology_fits` — one of the five written patterns actually fits
- `undocumented_cluster` — structure is there and none of the five names fit
- `looping` — the last queries repeated without a new ledger item
- `claim_supported` — asked later, once per SAR sentence, against the cited ledger item

**Choices** — relative, each list includes an escape:

- `next_walk`: `device` | `time` | `email` | `region` | `prior_cases` | `policy_text` | `none`
- `typology`: the five documented names | `undocumented` | `insufficient` | `likely_legitimate`

**Scores:**

- `closed_case_match` for the top structural neighbor
- `checklist_coverage`

Code then does only what code is good at:

```text
exposure            = sum of amounts on the implicated transactions
pattern             = typology choice, kept only if its probability clears
                      the threshold you measured on closed cases
if looping:         stop and escalate
if evidence_sufficient and not signals_contradict:
                    policy(ledger, pattern, exposure, reply) -> actions
if customer_reply_would_flip and we have not asked yet:
                    record nba_initial, ask once, then loop
if another_hop_useful and next_walk != none:
                    TigerGraph runs that one installed query, append to ledger, loop
else:
                    policy anyway, and the case says why we stopped short
```

Policy still emits `BLOCK_CARD` or `VERIFY_WITH_CUSTOMER`. Jev never sees those strings as options. That is not caution for its own sake. REFLEX and the judge paper both say this is the decision Jev loses: two near-valid actions, one of them irreversible, or a conclusion that takes several steps of arithmetic. Exposure thresholds and “customer denied, so block” are arithmetic and conjunctions. The fast brain should not re-derive them. It should hand the policy a clean pattern, a coverage score, and a contradiction flag.

The strong LLM is called twice, and only then:

1. Draft the case summary and, if policy filed, the SAR, using only ledger items.
2. Stop. Jev judges each draft sentence against its citation. Low `claim_supported` means the sentence is cut or rewritten. The narrative cannot outrun the graph.

When the case closes, Jev types the memory the way Jev-Mem types a write: which edges to draw from this case to devices, cards, and older cases, and whether the note is redundant with one we already stored. TigerGraph inserts those edges. Next case, Jev’s `next_walk` can choose `prior_cases` because that relation exists.

If confidence on `typology` or `evidence_sufficient` is low, do not average it into a fake “medium.” Escalate that question to the strong model or to the analyst, and store both answers on the case. That is the judge paper’s cascade, applied to a live investigation instead of to a benchmark.

Thresholds are fit on the closed four months. The twenty exam cases are not a tuning set. Pin `jev-1.13.0` (or whatever version you measured). `jev-latest` moves, and a moved probability silently moves your threshold.

### 4.6 What this is not

Jev does not replace TigerGraph. It cannot count a ring. It chooses **which** count to ask for, and **when** the counts are enough.

Jev does not replace the policy. A probability of fraud is not a block.

Jev does not write the SAR. It is a bad prose model on purpose. It is a good check that the prose stayed on the evidence, which is the workload JEV-as-a-Judge measured.

There is still no public RLCD paper. Do not describe the training recipe. Describe the interface and the four papers above.

---

## 5. What people already built for this exact brief

These are public HHGOA 2026 posts. They are competitors and teachers. Do not clone a repo. Steal the **separation of duties**, then make the uncertainty loop real.

### 5.1 The shared skeleton that keeps showing up

Every serious write-up converges on the same shape:

```text
vertices:  Customer, Card, Transaction, Device, EmailDomain,
           BillingRegion, ClosedCase
edges:     OWNS, MADE, FROM_DEVICE, PURCHASER_EMAIL, BILLED_IN,
           NEXT (time order on a card), ON_CARD, INVOLVES
queries:   shared device ring, velocity / card testing,
           out-of-region or impossible travel, similar closed cases,
           write the new case back
brain:     deterministic policy
mouth:     LLM narrative + SAR
face:      a case UI with evidence, uncertainty, NBA before/after, approval
```

[FraudGraph AI](https://dev.to/mokshith_118/fraudgraph-ai-building-an-agentic-graphrag-fraud-investigation-platform-with-tigergraph-and-18ag) is the most complete public map of the data model, a 10-tool MCP surface, a pure R1–R10 engine, LangGraph nodes, provenance tags (`graph | document | customer | external`), and the answer shape `{ case, sar, next_best_actions }`. They also show a local graph client with the same interface as live TigerGraph so tests run without Savanna.

[CaseGuard](https://dev.to/kanha_9650/-caseguard-winning-with-uncertainty-gated-agentic-fraud-investigation-on-tigergraph-407p) puts the uncertainty score in the **middle of a cycle**, not as a caption at the end. That is the piece FraudGraph-style linear graphs under-play.

[Tark](https://dev.to/mukull-s/a-fraud-investigation-agent-247l) adds the evidence compass (EVOI), a Bayesian log-odds ledger, and the hard rule that old cases inform the search and do not count as evidence.

[Divya Jain’s investigator](https://dev.to/divyajain14/building-an-agentic-fraud-investigator-with-tigergraph-moving-from-uncertain-signals-to-defensible-3nno) is the clearest statement of the product behavior: weak signals verify before blocking; a disputed subscription is not a block; a low score can still be a device ring; initial NBA and final NBA both exist; `CREATE_CASE` and `FILE_REPORT` are different acts.

### 5.2 Patterns worth detecting in GSQL

Documented in the dataset (five). Also hunt these, because the brief says not every pattern is documented:

| Pattern | Graph move |
| --- | --- |
| Card testing | Several small auths, then a larger one, short window, along `NEXT` |
| New device, card-not-present | This txn’s device is new for the card, and the device is young |
| Out of region / impossible travel | Billing region or geo jumps faster than travel allows |
| Account takeover | New device + new email domain + password-like or contact change if you have it, plus a burst |
| Shared-origin ring | One device, email, or proxy touching many cards or customers |
| Mule / pass-through | Fast in-and-out across linked accounts. Only if the data actually has the edges. Do not invent mule edges |
| Recurring legitimate | Same merchant, similar amount, stable interval. This **clears** a dispute |
| Undocumented cluster | Many cards, one device or email, closed cases on some of them, no typology name fits. Label `undocumented` and escalate |

Run these as installed queries that return counts, ids, and time bounds. The model names the pattern from those counts. If two patterns fire, keep both and let policy pick the stricter action.

### 5.3 What they are doing, and what we do that they cannot

Read them as four good analysts who each solved one part and left the brain as either a script or a chatbot.

| Team | What they actually built | Where it stops |
| --- | --- | --- |
| FraudGraph | The best map of the graph, ten fixed tools, a pure policy function, provenance, a legal answer file | Every case runs the same tool list. Their own numbers show the non-agentic GraphRAG gather **more** evidence items (8.9) than the agent (6.9), because nothing decides a hop is useless. Uncertainty is not in the loop |
| CaseGuard | A cycle that will not act under a confidence threshold, and a weighted formula for that confidence | The formula is four hand-picked weights. It cannot say “this closed case is the same shape” or “another device hop is worthless.” A weight is not a probability you measured |
| Tark | The right ledger, and the right question: which check is worth running. Old cases guide the search and do not count as proof | Something still has to **estimate** the value of the next check. They left that estimate informal. That estimate is a Jev score over the ledger |
| Divya’s investigator | The right product stories: weak score can be a ring, a subscription is not a block, initial action and final action both exist | The investigation is still “the model looked at the graph.” You cannot replay the branch that chose the device walk |

What we take from each, unchanged: FraudGraph’s schema and policy-as-code, CaseGuard’s before/after action, Tark’s ledger and the rule that memory is not evidence, Divya’s product behavior on weak scores and subscriptions.

What we add, which none of them have, because the papers are days old:

1. **The loop is a Jev call.** One state, the ledger. One batch of Nouls, one Choice of which graph to walk, one score of coverage. TigerGraph executes the walk Jev named. The case stores the probabilities, so a judge can see why the agent looked at devices and skipped region.
2. **Stopping is Jev-Mem’s rule**, not a fixed eight nodes. Sufficient, nothing critical missing, no contradiction — or another hop would not help. FraudGraph cannot skip work. A free LLM agent cannot prove it stopped for a reason.
3. **The SAR is guilty until Jev clears each sentence** against a ledger id. That is the judge paper’s evidence-grounded task, which is the task Jev matched GPT-6 on. Their SARs are fluent. Ours are checked.
4. **Undocumented is an option on the Choice**, with `insufficient` beside it, so a ring that matches none of the five write-ups is not forced into “card testing.” Choice without an escape hatch is how a decision model frames an innocent customer.
5. **Low confidence escalates that question only.** The rest of the case still runs. Their agents either trust the whole LLM trace or trust none of it.

We are not “an LLM agent plus a Jev classifier.” The classifier version is a bolt. If you delete Jev from FraudGraph, their pipeline still runs. If you delete Jev from this design, the next walk, the stop, the typology, and the sentence check have nothing to call. That is the test of “crucial.” Policy and GSQL remain, on purpose. They are the hands. Jev is the shift lead. The LLM is the person who types the report after the shift lead has signed the facts.

---

## 6. The agent to build

### 6.1 One picture

```text
                         ┌─────────────┐
   risk score / report / │  Dashboard  │
   analyst request       │  case view  │
                         └──────┬──────┘
                                │
                     ┌──────────▼──────────┐
                     │  LangGraph harness  │
                     │  checkpoints, caps  │
                     └──────────┬──────────┘
                                │  ledger is the state
                     ┌──────────▼──────────┐
                     │  Jev, one batched   │
                     │  call per cycle     │
                     │  Nouls + Choice +   │
                     │  Scores             │
                     └──────────┬──────────┘
            ┌───────────────────┼────────────────────┐
            ▼                   ▼                    ▼
     TigerGraph runs     policy commits        strong LLM writes
     the walk Jev named  the action            then Jev judges
            │                   │              each sentence
            └───────────────────┴────────────────────┘
                                │
                     probabilities stored on the case
                                │
                     Jev types the write-back edges
```

LangGraph is the harness: it remembers the cycle, enforces one customer question, and resumes after a crash. It does not decide. Jev decides the semantic branches. Delete Jev and this picture has no shift lead.

### 6.2 Nodes

| # | Node | Reads | Writes | Who decides |
| --- | --- | --- | --- | --- |
| 1 | Intake | Trigger | Case opened, ids | Code |
| 2 | First look | Ids | Txn, card, one-hop device. A small ledger, not every tool | Code, fixed. The controller needs something to look at |
| 3 | Cycle | Ledger | One Jev batch: sufficiency, contradiction, flip-if-asked, next walk, typology, coverage, loop | **Jev** |
| 4 | Walk | `next_walk` | One installed query’s claims appended to the ledger | TigerGraph. Skipped when Jev says `none` or another hop is not useful |
| 5 | Ask or act | Jev Nouls + exposure | `nba_initial`. Either one mock question, or straight to policy | Policy code, using Jev’s flags. Jev does not name the action |
| 6 | Reply | Mock API | Ledger item, source `customer` or `analyst`, then **back to cycle 3** | Code |
| 7 | Final action | Updated Nouls + policy | `nba_after_evidence`, `what_changed`, approval tier | Policy code |
| 8 | Write | Ledger + actions | Draft summary and SAR | Strong LLM |
| 9 | Clear the draft | Each sentence + its ledger id | Drop or escalate any sentence Jev will not support | **Jev as judge** |
| 10 | Remember | Final case | Edges Jev marked as worth storing; answer file | Jev types, TigerGraph writes |

If the cycle says the evidence is enough and a customer reply would not flip the action, the final NBA equals the initial one, and `what_changed` says no new evidence was required, with the Noul values that justified stopping.

### 6.3 Permissions

| Action class | Examples | Who may execute in the demo |
| --- | --- | --- |
| Read | All graph queries, policy lookup | Agent, always |
| Soft | Monitor, warn, verify, step-up, open case, close-as-clean | Agent, when policy says `auto` |
| Hard | Decline, block card, block all cards, file report | Agent may **recommend**. Execution is a mock that checks the approval tier and records `pending_approval` or `approved` |

The UI should show the approval queue. For the demo, click approve on one L2 action so the video contains a human gate, not only an autonomous run.

### 6.4 Answer file

Confirm the schema in the README. The public contract is three parts:

- **case** — trigger, entities, timeline of evidence, findings, belief, pattern, decisions, actions, status
- **sar** — present only when policy says file; who, what, when, where, how, why; every claim cited
- **next_best_actions** — initial list, final list, approval route for each, `what_changed`

Also upsert that case into the graph. The submission wants both the file and the vertex.

### 6.5 Interface

A single case page is enough:

- header: case id, trigger, pattern, belief, coverage, exposure
- timeline: evidence items in order, each with source
- a small subgraph picture: customer → card → txn → device, plus other cards on that device, plus linked closed cases
- two columns: NBA before evidence, NBA after evidence
- approval badges: auto / L1 / L2
- the explanation, with citations
- the SAR, when filed

Streamlit is an acceptable demo surface. A simple web page is also fine. Do not spend the last day on visual polish before the twenty answer files exist.

---

## 7. Build order

Do the steps in this order. Each step is demoable. Later steps must not weaken earlier guarantees.

### Step A — Read the dataset README and write nothing else

Inventory every file, the column you will actually use, the five typology docs, the policy doc, the closed-case columns, and the answer schema. Write a one-page data contract: primary keys, which id joins transaction to identity, what a “closed case” row contains. If you skip this you will invent columns.

### Step B — Graph that can answer analyst questions

Load a slice, then the full graph. Vertices and edges from §5.1. Prove four queries on one known closed fraud case and one known cleared case:

- history of the card,
- other cards on the same device,
- short-window velocity,
- prior cases touching the card.

If those four are wrong, no agent can be right.

### Step C — Policy function with tests

Encode the README rules as a pure function. Table-test the obvious branches: weak signal, customer denies, customer confirms, no reply, card testing, shared ring, subscription dispute, undocumented cluster, block-all forbidden. This is the highest-leverage test file in the repo.

### Step D — Linear investigation, no free agent

Wire nodes 1, 2, 5, 6, 10, 11. Fixed queries, policy, template explanation. Run all 20 cases. You now have schema-valid files. They will be naive. That is the baseline.

### Step E — Uncertainty, one question, before/after

Add belief, coverage, EVOI, the mock reply, and `nba_after_evidence`. Re-run the 20. Diff the files. The diff should be explainable in one sentence per case.

### Step F — Memory and undocumented patterns

Retrieve closed cases by shared device or email first. Add the `undocumented` label when a cluster is real and no typology fits. Confirm on the closed-case months that lookalike fraud and lookalike cleared cases pull belief in opposite directions **only through the prior**, and that a current-case device hit still moves belief on its own.

### Step G — Put Jev in the loop, then measure it

Replace the hand-written “what next” with the batched call in §4.5. On the closed months, check three things before you trust a threshold: when `typology` probability is above the cutoff, how often the closed-case pattern matches; when `evidence_sufficient` is high, how often the policy action matches what the analyst actually did; when `claim_supported` is high, how often a planted unsupported sentence is rejected. Keep the strong model as the escalation for low-confidence typology and for any SAR sentence Jev will not clear. Do not add `BLOCK_CARD` to a Choice.

### Step H — UI, replay, demo script

One case that is a clean fraud ring, one that must ask the customer, one that is a subscription dispute, one that escalates because the pattern is undocumented. The video is those four beats in 3–5 minutes, then a cut to the answer file and the case vertex in the graph.

### Step I — Submission bundle

Working agent, repo, 20 answer files, demo video, technical blog (what you built, architecture, how TigerGraph is used, agentic behavior, what you learned, what you would do with more time), and a public post tagging @TigerGraphDB that links the blog or the demo. One submission, team lead, no resubmit.

---

## 8. Rules of thumb you can check in code review

1. Can you regenerate the answer file from the evidence ledger and the policy version with the LLM disabled? If no, the LLM is doing a job that belongs to the ledger.
2. Does any prompt contain the words “decide whether to block”? Move that into the policy function.
3. Does every SAR sentence have a `ref`? If no, it does not ship.
4. Is there exactly one customer-facing question per case, and is the earlier NBA stored before the answer exists?
5. Can a prior case id appear in “why we looked” and stay out of “evidence that this txn is fraud”?
6. Are GSQL strings absent from the agent tool list?
7. Does a crash halfway leave a case you can resume, with no second block?
8. Did you fit thresholds on closed cases and leave `HHG-001`–`HHG-020` untouched until the final run?
9. Is `undocumented` a legal typology output?
10. Does the UI show uncertainty and both NBAs without reading the JSON by hand?

---

## 9. What you would be claiming, honestly

You can claim:

- TigerGraph runs the investigation math: traversal, velocity, rings, case memory.
- GraphRAG grounds the write-up in subgraph claims plus the policy passage that fired.
- The agent is a state machine with a stop, an evidence ledger, and a permission check.
- Uncertainty is a computed object that chooses whether to ask, and the ask is chosen because it can change the action.
- Jev is the control plane: one batched call per cycle chooses the next graph walk, the pattern (including undocumented), whether to stop, and whether each SAR sentence is supported. Low confidence escalates that question.
- Policy code is the only component that names a block, a verify, or a report. The LLM writes prose and does not get a vote on the action.

You should not claim:

- That the agent “detects fraud” as a classifier. The dataset has no exam labels you are allowed to treat as a training target.
- That Jev is an open, fully documented model. The weights and RLCD recipe are unpublished. REFLEX is the paper; the vendor blog is a claim.
- That a public team’s dollar thresholds are the official policy. The README is.

---

## 10. Sources

Jev, as the control plane:

- Almeida, *Introducing System One models & Jev*, TypeSafe AI, September 2026. https://typesafe.ai/blog/introducing-system-one-models-and-jev
- Wu and Lim, *REFLEX with Jev for Efficient Selective Control in LLM Agents*, arXiv:2609.26532. https://arxiv.org/abs/2609.26532
- Jiang, Li, and Li, *Jev-Mem: System-One-Controlled Agentic Memory*, arXiv:2609.23986. https://arxiv.org/abs/2609.23986
- Li, Miao, Krishnan, and Padman, *JEV-as-a-Judge: Accept When Confident, Escalate When Unsure*, arXiv:2609.26550, 21 September 2026. https://arxiv.org/abs/2609.26550
- Cheng, Dai, and Sun, *The smart if-statement* (this-that-model-1.0), arXiv:2609.23886. https://arxiv.org/abs/2609.23886
- Learn Jev, *Building an agent harness* and *Noul, Choice and Score*. https://learnjev.com/tutorials/agent-harness and https://learnjev.com/tutorials/three-primitives
- LangChain, *Building a Harness with Jev*. https://www.langchain.com/blog/building-a-harness-with-jev
- Arize, *TypeSafe Jev: Can Decision Models Replace LLM Judges?*, September 2026. https://arize.com/blog/typesafe-jev-llm-judge/
- Anthropic, *Building effective agents*. https://www.anthropic.com/engineering/building-effective-agents
- Anthropic, *Writing effective tools for AI agents*. https://www.anthropic.com/engineering/writing-tools-for-agents
- TigerGraph MCP. https://github.com/tigergraph/tigergraph-mcp

Same-hackathon practice (use as maps, verify every rule against the dataset README):

- FraudGraph AI. https://dev.to/mokshith_118/fraudgraph-ai-building-an-agentic-graphrag-fraud-investigation-platform-with-tigergraph-and-18ag
- CaseGuard. https://dev.to/kanha_9650/-caseguard-winning-with-uncertainty-gated-agentic-fraud-investigation-on-tigergraph-407p
- Tark. https://dev.to/mukull-s/a-fraud-investigation-agent-247l
- Divya Jain, Agentic Fraud Investigator. https://dev.to/divyajain14/building-an-agentic-fraud-investigator-with-tigergraph-moving-from-uncertain-signals-to-defensible-3nno

Background that REFLEX itself relies on: ReAct, FrugalGPT, RouteLLM, BFCL, τ-bench / τ²-bench. Read REFLEX §2 before chasing those papers. The fraud-specific design does not require them.

Math and graph algorithms for the decomposed pipeline (§11):

- Bahnsen, Stojanovic, Aouada, Ottersten, *Cost Sensitive Credit Card Fraud Detection Using Bayes Minimum Risk*. The action threshold comes from the cost of a wrong block versus a missed fraud, not from 0.5.
- Wald, *Sequential Analysis* (1945). The sequential probability ratio test is the binary ancestor of “stop when the evidence crosses a line.”
- Naghshvar and Javidi, and the 2025–2026 cost-aware sequential hypothesis testing papers (CASHT, arXiv:2512.19067; non-homogeneous costs, arXiv:2509.11632). Pick the next check by expected information per expected cost. A one-step “bits per buck” score is the wrong ratio.
- Aamodt and Plaza, *Case-Based Reasoning: Foundational Issues* (1994). Memory is retrieve, reuse, revise, retain.
- TigerGraph Graph Data Science library: `tg_wcc`, `tg_louvain`, `tg_pagerank_pers`, `tg_cosine_nbor_ss`, `tg_fastRP`. https://github.com/tigergraph/gsql-graph-algorithms
- Chen and Guestrin, FastRP (2020), as implemented by TigerGraph. Embeddings are an offline index for memory, not a per-case detector.

---

## 11. The pipeline taken apart, and the best technique in each part

The brief is eight jobs. Competitors fold them into one LangGraph script and one language model. Each job has a technique that was built for it. Mixing them is how a weighted “confidence” number appears: four different questions crushed into one score.

Eight planes. Each owns one kind of work. A plane may read another plane’s output. It does not redo that plane’s job.

| Brief step | Plane | Best technique | What the other teams use | Leave this out |
| --- | --- | --- | --- | --- |
| Trigger | Intake | Typed event: `risk_score`, `customer_report`, `analyst_request`. The type chooses the first question, not the verdict | A single “alert” object | Letting the risk score skip the investigation |
| Investigate, gather from the graph | Graph measure | One installed query or one GDS algorithm per pattern, returning counts and ids | The same 8–10 queries on every case | PageRank on all transactions. Betweenness on a graph that has no money-flow edges. A GNN trained this week |
| Pattern and risk level | Belief | Calibrated prior, then Bayesian log-odds. Each evidence type adds a likelihood ratio measured on closed cases | A weighted sum of “graph support” and the raw risk score | Treating the bank score as a probability. Averaging in the outcome of a similar old case as if it were evidence about this card |
| Is there enough, and what is missing | Control | Jev Nouls for sufficiency, contradiction, and “would this answer flip the action.” Scores for coverage | A hand-tuned weight, or the LLM saying it feels sure | A Choice that must pick an action even when none fits |
| Which extra evidence | Decision, information | Expected value of sample information, divided by the policy cost of that ask | Run every remaining tool, or ask the customer whenever confidence &lt; 0.6 | “Bits per buck” on a single imagined answer |
| Next action, approval, stop | Decision, action | Bayes minimum risk over the legal action set. Policy deletes illegal actions before the min is taken | If-statements on a probability, with 0.70 copied from a blog | Jev or the LLM choosing `BLOCK_CARD` |
| Explain | Language | Ledger citations, plus the counterfactual of running the same policy on the other customer reply. Jev judges each sentence | An LLM narrative | A sentence with no ledger id |
| Case memory | Memory | Case-based reasoning. Retrieve by shared entities and by an offline embedding. Retain by writing edges Jev marked | TF-IDF over analyst notes | Using the retrieved case’s verdict as proof |

LangGraph is not a plane. It is the harness: checkpoint, one customer question maximum, resume after a crash, hard step cap. It stores the ledger. It does not score, walk, or decide.

### 11.1 Graph measure: the algorithm that matches the pattern

A pattern is a measurement. The measurement runs in GSQL. Jev only chooses which measurement is worth running next.

| Pattern | Measurement | Why this one |
| --- | --- | --- |
| Shared device or email ring | 2-hop count from the seed card through `Device` or `EmailDomain`, plus `tg_wcc` on the card–device projection to name the component | A ring is a connected component. You want the member ids and the size, not a popularity rank |
| Undocumented syndicate | `tg_louvain` **offline**, on the card–device–email graph, community id stored on the card. At investigation time, read the community and the fraction of its cards that appear in confirmed closed cases | Louvain over 590k nodes does not belong on the request path. The community id is a feature you computed once. A community the typology doc does not name, with confirmed cases inside it, is the `undocumented` label |
| Who around this card matters | `tg_pagerank_pers` seeded at the card, on the local neighborhood, top-k only | Personalized PageRank ranks neighbors of **this** card. Global PageRank ranks popular merchants. Those are different questions |
| Card testing | Window accumulator along `NEXT`: count of amounts under the policy’s micro-auth line inside the policy’s time window, then a larger amount | This is a sequence. No centrality algorithm sees it |
| Impossible travel or new region | Along `NEXT`, compare billing region and timestamp to the card’s usual region | A distance check. Cosine similarity does not know about time |
| New device, card not present | Is this `Device` absent from the card’s earlier transactions, and how many other cards does it touch | A set-membership query |
| Similar card behavior | `tg_cosine_nbor_ss` from the seed, on a small feature vector you attach to the card (region histogram, amount band, channel mix) | Neighborhood cosine answers “who transacts like this card.” It is a retrieval key, not a fraud score |
| Case memory index | `tg_fastRP` **offline** on the same projection, cosine against closed-case cards at retrieve time | FastRP is a cheap structural embedding. Train no GNN. The exam set has no labels you are allowed to fit a deep model on |

Do not run Louvain, FastRP, or PageRank inside the per-case loop. Precompute community id and the embedding. The case loop only reads them and runs the cheap seeded queries.

### 11.2 Belief: log-odds, with a prior you calibrated

The bank’s risk score is a rank. On the closed four months, fit a map from score bin to the fraction of cases that were confirmed fraud (isotonic regression is enough; a straight line if the bins are monotone). That fraction is the prior `p0`. Convert once:

```text
log_odds = log(p0 / (1 - p0))
```

Each new evidence item has a type the query already named: `device_shared_ge_5`, `micro_auth_burst`, `region_jump`, `customer_denies`, `looks_like_subscription`. On closed cases, count how often that type appears in confirmed fraud and in cleared cases.

```text
LR = P(evidence type | confirmed) / P(evidence type | cleared)
log_odds = log_odds + log(LR)
p = 1 / (1 + exp(-log_odds))
```

Cap each LR with a floor and a ceiling so one rare bin cannot send `p` to 0 or 1. Store `log_odds`, `p`, and the list of LRs on the case. That list is the risk explanation.

A similar old case contributes its outcome **only** to the prior, as a second small prior you can show separately: “among closed cases in this Louvain community, 80% were confirmed.” Add that as its own LR only if you measured it as a feature on closed cases and you label it `prior_from_memory`. It is not an observation of this transaction. Tark’s rule, in the update equation.

Contradiction is two LRs that pull hard in opposite directions, or a customer confirm against a large device component. Record it as a flag. Do not blend it away. Dempster–Shafer theory is the textbook tool for “conflict is its own mass,” and it is the wrong engine here: the combination rule is hard to explain, and one paradox (Zadeh) makes two strong disagreeing sources produce a confident third answer. A flag the policy can see is the version a fraud lead can audit.

### 11.3 Action: Bayes minimum risk, inside the legal set

Bahnsen and coauthors showed, on card fraud, that acting at `p > 0.5` does not minimize loss. The threshold moves with the cost of blocking a good customer versus missing a fraud.

For this brief the choice is not yes/no. For each action the policy still allows (verify, monitor, decline, block, block-all, warn, file, escalate, close-clean):

```text
cost(action) = p * loss(action if this is fraud)
             + (1 - p) * loss(action if this is legitimate)
pick the action with the smallest cost
```

The losses are a small table you write down and version: blocking a legitimate card is a high customer-harm loss; leaving a ring open is a high loss times exposure; asking the customer is a small delay loss; filing a report has a process loss plus a large miss-penalty if you should have filed and did not. Fit the **ratios** on closed cases if you can, because only ratios change the argmin. The README’s mandatory actions override the table. If the policy says “customer denies ⇒ block,” that action is the only legal one, and minimum risk is not consulted.

Approval tier is not a cost. It is a permission. The chosen action still carries `auto`, `L1`, or `L2` from the policy. The mock executor refuses to perform an L2 action without the approval token.

### 11.4 What to ask next, and when to stop

Wald’s sequential probability ratio test says: keep sampling until the likelihood ratio crosses an upper line or a lower line, and the lines are set by how many errors you tolerate. That is the right ancestor for a binary “fraud or not” stop. This case has many actions and asks that cost different things (a graph query is cheap, a customer ping is not, an analyst hour is expensive). The generalization used in cost-aware sequential testing is:

```text
value(question) = cost(best action now)
                - average over the question's possible answers of
                  cost(best action after that answer)
ask the question with the largest value / cost(question)
stop when every remaining question has value <= cost
```

The average is the expected value of sample information. Estimate the possible answers from closed cases: for `ask_customer`, the answer rates are the confirm rate and deny rate among closed cases with this pattern. For `walk_device`, the answer is “component size bucket,” and you already know how often each bucket appears.

The 2025 result on non-homogeneous costs matters for the implementation. Maximize **expected information divided by expected cost**. Do not score each question by a single imagined best answer divided by its cost. That “bits per buck” shortcut looks at the lucky answer and over-asks.

Jev’s `customer_reply_would_flip` and `another_hop_useful` are the same question when you do not yet have a stable LR table. Once the table exists, the formula above replaces the Noul for **which** question, and the Noul remains the check that the formula’s inputs are not nonsense. One customer-facing ask per case, because the submission wants one before and one after.

Stop also fires on the harness caps: one ask already used, loop Noul high, or max cycles. Those are safety stops. The value test is the decision stop. Write which one fired into `what_changed`.

### 11.5 Memory: retrieve, reuse, revise, retain

Aamodt and Plaza’s cycle is the whole memory section of the brief, with the names they used.

| Step | In this agent |
| --- | --- |
| Retrieve | Shared device, email, or Louvain community first. FastRP cosine second, only to rank notes inside that set. TF-IDF only if both structural lookups are empty |
| Reuse | The retrieved cases tell you which measurement the analysts ran, and the community’s confirmed rate becomes `prior_from_memory`. They do not enter the ledger as proof |
| Revise | If the human overrides the action, store the override as the outcome. The agent’s first recommendation stays in the timeline and is not rewritten |
| Retain | On close, Jev marks which edges are worth drawing. TigerGraph writes the case vertex, those edges, and the community link. The next retrieve can walk them |

### 11.6 Explanation, as a consequence of the other planes

The narrative is allowed to say four things, each already computed:

- the evidence types and their LRs
- the question that was asked, and its value versus its cost
- the action that won minimum risk, the runner-up, and the rule that made other actions illegal
- the counterfactual: run the policy once more on the opposite customer reply and report that action. That is why the ask was worth it

Jev’s `claim_supported` Noul runs on each sentence against its ledger id. A sentence that fails is cut. The strong model does not get a second vote on `p` or on the action.

### 11.7 What “best” does not mean this week

A graph neural network, a trained multi-hypothesis sequential test with learned action costs, and a full Dempster–Shafer stack are real techniques. They need labels, time, and a calibration set you must not build from `HHG-001`–`HHG-020`. The closed four months support likelihood ratios, an isotonic map of the risk score, Louvain and FastRP computed once, and a small loss table. That set is the best technique that can be finished, tested, and explained on the demo. Anything heavier that is not measured on the closed months is a slide, not a control plane.

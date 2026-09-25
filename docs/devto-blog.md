---
title: "Jev × TigerGraph: The Fraud Agent That Looks Once"
published: false
description: "Jev holds the gates. TigerGraph holds the facts. A fraud investigation agent that walks the graph, updates a chance, and stops when the evidence is not enough."
tags: jev, tigergraph, fraud, graphrag, agents
---

Jev decides when to look. TigerGraph decides what is true.

We built a fraud investigation agent on that split. An alert comes in. TigerGraph returns the card, the device, and the older cases. Jev is allowed three questions. A rule book writes the next action. A language model explains the case after the decision is already made.

Repository: YOUR_REPO_URL
Demo: YOUR_VIDEO_URL

## What we built

An agent that takes one card alert and produces a case a person can sign.

The alert is a customer dispute, a high bank score, or an analyst request. There is no fraud flag on the transaction. The agent gathers evidence, names a pattern when the measurements support one, and recommends what to do next. A block, a decline, or a report waits for a signature. Everything else can proceed on its own.

The run leaves three things behind: an answer file, a case vertex in TigerGraph, and a desk that shows the investigation from the alert to the approval. The desk talks only to an API. The API starts the run, reads the case, or resumes it when someone signs. It does not pick the action.

## The architecture

One case. One direction. Each stage has one owner.

{% mermaid %}
flowchart TB
  subgraph row1 [Gather]
    direction LR
    intake["Intake<br/>Dispute, bank score, or analyst. One case row."] --> graph["Graph<br/>Official MCP. Same pack every case: charge, device, region, older cases, exposure."]
    graph --> belief["Belief<br/>Prior is the bank score. Each fact adds a log-odds weight. Chance is the sigmoid."]
    belief --> pattern["Pattern<br/>Fixed checks lock the name. If not, Jev names it. Top two too close: name stays blank."]
  end
  subgraph row2 [Decide]
    direction LR
    hop["Jev hop<br/>One more query, or none: other cards, shared devices, older cases, or the policy note."] --> policy["Policy<br/>R1 to R10, pass 1. One assumed reply. Pass 2 writes the final actions."]
    policy --> verdict["Verdict<br/>Real purchase, unnamed shape, or chance high enough. Otherwise uncertain. Card stays open."]
    verdict --> close["Close<br/>Name the fact it rests on. Jev keeps a sentence that quotes a fact. Sign a block, decline, or report. Write ExamCase and read it back."]
  end
  pattern --> hop
{% endmermaid %}

| Plane | Who owns it |
| --- | --- |
| Facts | TigerGraph. Installed GSQL. Official MCP. |
| Chance | A Bayesian update. The bank score is the prior. Each finding moves the log-odds. |
| Pattern | Fixed checks first. Jev only when those checks leave the name blank. |
| Actions | A fixed rule book, run twice. Before the customer answer, and after it. |
| Words | A language model rewrites claims the graph already returned. |
| Control | Jev, pinned at `jev-1.13-free`. Three gates. No action button. |
| Memory | An `ExamCase` vertex. It counts only after a read-back matches. |
| Resume | A checkpoint after every step. A crash does not ask twice. |

The chance is a sigmoid of the log-odds. Worrying facts push it up. A long quiet history, a trip, or a monthly charge pulls it down. Older cases guide the search. They are not proof of this charge.

The verdict is three questions, in order. Did the rules close it as a real purchase? Is the shape one the bank never named? Is the chance high enough to call fraud? If none of those fire, the case stays uncertain, and the card stays open. A named pattern does not skip those questions.

## How TigerGraph is used

The graph is `HHGOA`. The agent never writes GSQL at runtime. Official TigerGraph MCP is the door. The tool is one installed query, called by name.

{% mermaid %}
flowchart LR
  door["Official MCP<br/>run_installed_query by name"] --> pack["Installed pack, every case<br/>txn_and_card, card_window, device_profile, device_neighbors, identity_flag, region_history, recurring_match, prior_cases, exposure_episode"]
  pack --> hop["One hop, Jev picks<br/>component_cards, card_community, prior_cases, policy_vector_search, or none"]
  hop --> save["ExamCase write<br/>Verdict, pattern, exposure. Edges ON_CARD, EXAM_OTHER, EXAM_TXN, EXAM_DEVICE. Read-back must match."]
{% endmermaid %}

Every case runs the same pack: the flagged charge, the card history, the device and who else used it, the regions, a repeating amount, older cases, and the money in the episode. The pack is invariant so a model cannot skip a check.

Jev may then spend one more query.

- Other cards on this device.
- A bounded walk across devices that a few charges share.
- Older cases, again.
- One policy note. TigerGraph `vectorSearch` on `PolicyNote.vec` returns the closest paragraph. That paragraph is context for the writer. It is not a new fact about the charge.

When the case is finished, the verdict and the exposure are written to an `ExamCase` vertex and tied back to the card, the other cards, the purchases, and the device. The vertex is read back. It counts only when the two copies match. The next investigation can retrieve it.

## What the agent is allowed to do

The budget is fixed. One pack. One extra lookup. One assumed customer answer. One rewrite of the sentences.

Jev answers three questions.

1. If the pattern checks did not lock a name, which shape is this, and how sure is each option? If the top two are too close, the name stays blank.
2. Is one more graph lookup worth it, and which one?
3. Does each sentence quote a fact already on the case?

If Jev does not answer, the miss is recorded. The rules still choose the actions.

The rules run twice, so new evidence can change the plan. The first list stays on the file. The replies we did not assume stay too, marked as not what happened. The case also names the one fact the decision rests on: remove that family, rerun the rules, and the actions change.

A block, a decline, or a report waits for a person. Open, watch, warn, and close can proceed on their own. Signing an action that is not on the final list is refused.

## What we learned

The graph has to run first, and it has to run the same queries every time. If the model chooses what to fetch, it can miss a shared device or a run of tiny charges.

A vector search and a graph walk answer different questions. The vector index finds the policy paragraph. The walk finds the other cards. The writer should see one short passage beside the claims, not the raw transaction table.

A customer message opens the case. It is a dispute. The denial that can authorize a block is a later answer, and the agent assumes at most one.

Memory is the vertex you can read back. A write you do not read is a log. The next case cannot use it.

Uncertainty is a finished decision. Mixed evidence gets a next action, not a forced fraud call.

## What we would do with more time

Fit the chance map on the earlier closed cases, freeze it, and leave the scored alerts out of the fit. Today the prior is the bank score, and the weights are fixed.

Run a community algorithm once, offline, and store the community on the card. The walk we ship finds shared devices. A stored community would catch the shapes the bank never named.

Require Jev on the scored run, so each unlocked gate shows its probability map. A recorded miss should be the exception.

Let new investigations land in the graph after the scored set, and let the next case retrieve them the same way it retrieves older closed cases.

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
  subgraph intake [Intake]
    direction LR
    dispute[Customer dispute] --> open[One case row]
    score[Bank score] --> open
    analyst[Analyst request] --> open
  end

  subgraph graph [Graph engine]
    direction LR
    mcp[Official MCP] --> hist[Charge and card history]
    hist --> device[Device, neighbors, identity]
    device --> place[Region and monthly amount]
    place --> older[Older cases and exposure]
  end

  subgraph belief [Belief engine]
    direction LR
    prior[Prior is the bank score] --> weights[Each fact adds a log-odds weight] --> chance[Sigmoid chance]
  end

  subgraph pattern [Pattern engine]
    direction LR
    detect[Five named shapes plus unnamed] --> locked{Detector locked a name?}
    locked -->|Yes| kept[Keep it. Jev is not asked]
    locked -->|No| pgate[Jev pattern gate]
    pgate --> split{Top two within 0.1?}
    split -->|Yes| blank[Name stays blank]
    split -->|No| picked[Take the leading name]
  end

  subgraph hop [Control engine · Jev hop]
    direction LR
    choose{One more query?}
    choose -->|device| cards[Other cards on this device]
    choose -->|community| walk[Shared-device walk]
    choose -->|memory| again[Older cases]
    choose -->|policy| vec[Closest policy note]
    choose -->|none| none[Stop walking]
  end

  subgraph policy [Policy engine]
    direction LR
    pass1[Pass 1 · R1 to R10 · no reply yet] --> ask{Still need the customer?}
    ask -->|Yes| reply[Reply engine assumes one answer]
    reply --> pass2[Pass 2 · final actions]
    ask -->|No| pass2
  end

  subgraph verdict [Answer]
    direction LR
    v1{Closed as a real purchase?} -->|Yes| legit[Legitimate]
    v1 -->|No| v2{Unnamed shape?}
    v2 -->|Yes| fraud[Fraud]
    v2 -->|No| v3{Chance high enough?}
    v3 -->|Yes| fraud
    v3 -->|No| unsure[Uncertain · card stays open]
  end

  subgraph close [Stop · language · memory]
    direction LR
    commit[Point of commitment] --> draft[Language engine writes from the claims]
    draft --> sentence{Sentence quotes a fact?}
    sentence -->|Yes| hold[Jev keeps it]
    sentence -->|No| swap[Replace it with the claim]
    hold --> route{Block, decline, or report?}
    swap --> route
    route -->|Yes| person[Wait for a signature]
    route -->|No| auto[Proceed on its own]
    person --> save[Upsert ExamCase]
    auto --> save
    save --> back{Read-back matches?}
    back -->|Yes| stored[Next case can retrieve it]
    back -->|No| refused[Case is not submitted]
  end

  open --> mcp
  older --> prior
  chance --> detect
  kept --> choose
  blank --> choose
  picked --> choose
  cards --> pass1
  walk --> pass1
  again --> pass1
  vec --> pass1
  none --> pass1
  pass2 --> v1
  legit --> commit
  fraud --> commit
  unsure --> commit
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
  subgraph door [Door]
    direction TB
    mcp[Official MCP]
    tool[run_installed_query by name]
    mcp --> tool
  end

  subgraph schema [Graph HHGOA]
    direction TB
    txn[Transaction]
    card[BankCard]
    phone[DeviceProfile]
    closed[ClosedCase]
    ident[IdentityFlag]
    note[PolicyNote with vec]
    exam[ExamCase]
  end

  subgraph links [Edges]
    direction TB
    e1[TXN_ON_CARD]
    e2[FROM_DEVICE]
    e3[CASE_ON_CARD]
  end

  subgraph pack [Installed pack · every case]
    direction TB
    q1[txn_and_card · card_window]
    q2[device_profile · device_neighbors · identity_flag]
    q3[region_history · recurring_match]
    q4[prior_cases · exposure_episode]
  end

  subgraph second [One hop · Jev picks]
    direction TB
    h1[component_cards]
    h2[card_community]
    h3[prior_cases]
    h4[policy_vector_search then policy_passage]
    h5[none]
  end

  subgraph memory [Write and read back]
    direction TB
    w1[ExamCase · verdict, pattern, exposure]
    w2[ON_CARD · EXAM_OTHER · EXAM_TXN · EXAM_DEVICE]
    w3[GET the vertex · same verdict and money]
    w1 --> w2 --> w3
  end

  tool --> q1
  txn --> e1
  e1 --> q1
  note --> h4
  exam --> w1
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

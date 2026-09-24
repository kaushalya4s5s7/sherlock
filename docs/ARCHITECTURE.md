# Architecture

The agent that can be submitted. Stress-tested against `HHGOA_IEEE 2/README.md` and the closed-case file. Where this document and `info-research.md` disagree, this document wins, because it follows the policy text and the answer schema.

Deadline is the twenty JSON files, the case vertices in TigerGraph, a UI that shows one investigation end to end, and the write-ups. Optional alerts beyond the twenty go in a separate folder and do not block the exam run.

## What the README forces

Each exam case emits one file, `cases/<case_id>.json`, with:

- `case` — status, verdict, probability, pattern, evidence, exposure, prior-case ids, and `written_to_graph: true` only after the vertex is read back
- `sar` — filed only when `FILE_REPORT` is in the final actions; otherwise an empty report
- `next_best_actions.initial` — before any simulated reply
- `next_best_actions.final` — after the reply, or equal to `initial` when nothing was asked
- `evidence_requests` — the assumption, because no customer replies are in the data
- `stop_reason`, `tool_calls`, `tokens`, `latency_s`

`fraud_probability` is scored for calibration. `uncertain` is a full-credit verdict when the actions follow R1 and R8. Half the exam cases are legitimate. IDs that are not in the dataset score zero. The example JSON in the README uses illustration ids (`T0412877`, `C00377`). Those ids are not HHG-017. The validator rejects them.

Action names and routes are exact:

| Route | Actions |
| --- | --- |
| `auto` | `ALLOW_TRANSACTION`, `MONITOR_CARD`, `MONITOR_CONNECTED_CARDS`, `WARN_CUSTOMER`, `VERIFY_WITH_CUSTOMER`, `STEP_UP_AUTH`, `GENERATE_REPORT`, `CREATE_CASE`, `ESCALATE_TO_ANALYST`, `CLOSE_NO_FRAUD` |
| `L1` | `DECLINE_TRANSACTION`; `BLOCK_CARD` when exposure ≤ $2,500 |
| `L2` | `BLOCK_CARD` when exposure > $2,500; `BLOCK_ALL_CARDS`; `FILE_REPORT` |

The agent may execute only `auto`. `L1` and `L2` are recommended and wait.

## What the closed cases already teach

5,565 closed investigations, July–October. 4,665 confirmed, 900 cleared.

| Outcome | Actions the analysts actually took | Count |
| --- | --- | --- |
| Confirmed, no report | `CREATE_CASE`, `BLOCK_CARD` | 4,268 |
| Confirmed, report filed | `CREATE_CASE`, `BLOCK_CARD`, `FILE_REPORT` | 397 |
| Cleared | `VERIFY_WITH_CUSTOMER`, `CLOSE_NO_FRAUD` | 900 |

Every cleared case was a high score that the cardholder then confirmed: travel, or a new phone. Exposure on those rows is 0. A score of 0.9 is the start of a legitimate case, not the end of one.

Reports are rare. They are filed when exposure is large **or** the activity shares a device with other victims, including nine `undocumented` cases. Two undocumented shapes are already in the notes, and the exam can contain them again:

- Samsung SM-G935F, Chrome for Android, anonymous proxy, many cardholders in the same month. Confirmed, reported, even when exposure is about $100. Pattern name in the file is `undocumented`, not `card_not_present_new_device`.
- Four online purchases in about forty minutes, each just under $500. Structuring under an authorization limit. Also `undocumented`.

`card_testing` is real and rare: 16 closed cases. The detector still runs on every card, because R5 is a hard rule.

Do not fit anything on `HHG-001`–`HHG-020`. Fit the score map and the likelihood ratios on July–September. Check calibration on October. Freeze the tables. Then run the exam once.

## Stress test of the earlier design

| Earlier idea | What breaks against this README | Replacement |
| --- | --- | --- |
| Jev chooses the next graph walk, including the first one | A bad or skipped call misses card testing, a region jump, or the SM-G935F ring. Those are mandatory measurements, not optional curiosity | A fixed measurement pack runs first. Jev chooses only the second hop and whether the pack is already enough |
| Jev or a cost table names `BLOCK_CARD` | R1–R10 name the actions. A cost table that overrides R7 will block a subscription. A cost table that overrides R2 will fail to block after a denial | Policy function is the only action emitter. Bayes minimum risk breaks ties inside the set of actions the rules already require or allow |
| One confidence weight | Stopping is defined: probability ≥ 0.85 or ≤ 0.15 **and** two independent evidence items; or a verification settles it; or more steps would not change the decision | Three separate numbers: `p`, independent-evidence count, and the value of the next ask |
| Simulated reply written by the LLM | The model can deny every dispute and manufacture fraud. Cleared history says the opposite: many disputes and high scores are confirmed by the customer | The reply is a pure function of the ledger. The assumption text is stored in `evidence_requests` |
| Ask the customer on every ambiguous case, then add 0.3 to `p` | `fraud_probability` is scored for calibration. A hand-added jump is not a likelihood | Denial and confirmation have likelihood ratios counted from closed-case notes, or a frozen modest shift measured on October. They do not set `p` to 0.99 |
| File a report on every confirmed fraud | 4,268 confirmed cases did not file. Filing is R2’s extra conditions, R6, or R9 | `FILE_REPORT` and `sar.file` are set by one predicate |
| `written_to_graph: true` after a local dict write | The brief wants the case in TigerGraph, retrievable by the next case | True only after a read-back of the vertex by id |
| Copy the README example into HHG-017 | The example ids are not in the case pack | Schema test plus an id-existence test |
| Customer message “I never made this” is already R2 | That message is the trigger. R2 is the verification reply. R7 is checked first, because a dispute that matches a recurring charge must not be blocked | Rule order below |
| Louvain or FastRP inside the request | 590k transactions. The exam run has to finish and be explainable | Community id and FastRP are offline columns. The case reads them |

## Planes

```text
case_pack row
    │
    ▼
Intake ───────────── trigger type, txn, card, customer
    │
    ▼
Measurement pack ─── TigerGraph installed queries, every case
    │                 (sequence, device, region, recurring, prior cases)
    ▼
Belief ───────────── calibrated prior + log-odds
    │
    ▼
Policy, pass 1 ───── initial actions, routes, whether an ask is required
    │
    ├── no ask ────── final = initial
    │
    └── ask ───────── Reply simulator (pure function)
                          │
                          ▼
                     Belief update + Policy, pass 2
    │
    ▼
Stop predicate ───── README §6, written into stop_reason
    │
    ▼
Language ─────────── summary + SAR draft from the ledger only
    │                 Jev judges each sentence
    ▼
Memory write ─────── case vertex, edges, read-back
    │
    ▼
cases/HHG-0xx.json
```

LangGraph is the harness around this. It checkpoints after each plane, caps the ask at one, and resumes after a crash. It does not pick an action.

Jev is the control plane on three decisions the rules do not already compute:

1. After the measurement pack, is a second hop worth it (`another_hop_useful`, and a Choice of `device_component` / `community` / `prior_cases` / `policy_text` / `none`)?
2. Is the verdict `undocumented` rather than a forced known pattern, given the pack?
3. After the draft, does each sentence follow its cited evidence item?

Low confidence on (2) escalates that question to the strong model and stores both answers. It does not change the action list. The action list is the policy function.

### 1. Intake

One row of `case_pack.csv`. `trigger_type` is `risk_score` (11 cases), `customer_report` (8), or `analyst_request` (1, HHG-014). The flagged transaction is where the alert fired. It may not be where the episode started, and it may not be fraud.

A customer report is a dispute. It opens the R7 check. It is not yet a verification denial.

### 2. Measurement pack

Installed queries through TigerGraph MCP. Same pack for every case, so a control-model miss cannot skip a rule. Each query returns ids that already exist, a one-line claim, and a `ref`. Empty is a finding (“no other card on this device”), stored as evidence with source `graph`.

| Query | Serves |
| --- | --- |
| `txn_and_card` | Flagged transaction, amount, channel, product, region, risk score, customer’s other cards |
| `card_window` | Ordered `NEXT` window: card testing (3+ online amounts under $5 inside 1 hour, then a larger one), structuring (several online amounts just under $500 inside an hour), burst of 2–4 online purchases inside 48 hours |
| `device_profile` | Online only. `id_15` New/Found, `id_23` proxy, OS, browser, screen, DeviceInfo. Profile string is `DeviceInfo \| OS \| browser \| screen`, matching the answer example |
| `device_neighbors` | Other cards on that profile, and closed cases on those cards |
| `region_history` | This card’s billing regions before the flagged time. A new region for several days with home activity continuing is a trip only when home continues; a new region with no home history is out-of-region use. In-person is product `W` |
| `recurring_match` | Same amount band, similar spacing, earlier months on this card. R7 |
| `prior_cases` | Closed cases on this card, this device, this customer. Ids for `similar_prior_cases` |
| `exposure_episode` | Transaction ids the pack believes are one episode. Exposure is the sum of absolute `TransactionAmt`. Legitimate verdict forces this list empty and exposure 0 |

Second hop, only if Jev says it is useful or the pack already shows a shared profile:

| Query | When |
| --- | --- |
| `component_cards` | Device or email touches more than one customer. This is the SM-G935F check and R6 |
| `community_lookup` | Read the offline Louvain id. If the community has confirmed closed cases and matches no named pattern, pattern becomes `undocumented` |
| `policy_passage` | TigerGraph vector search over this README’s pattern section, the policy, and the closed-case notes. Returned text is cited as source `document`. It is not a new fact about the transaction |

Offline, once, before any exam case: Louvain and FastRP on the card–device–email projection, stored as attributes. Personalized PageRank is not on the exam path. Global PageRank is not used.

V, C, D, M, and numeric id columns may be used as unnamed signals. The claim must say they are unnamed Vesta features. They never appear as a fake definition.

### 3. Belief

Prior: isotonic map from `risk_score` bin to confirmed rate, fit on July–September. A customer report with no score uses the confirm rate of disputed closed cases, not 0.5 by habit. October is the calibration check. The map is a file, loaded by hash, not refit during the exam.

Each measurement adds `log(LR)` with LR = P(finding | confirmed) / P(finding | cleared), floored and capped, counted on the same months. Findings are coarse on purpose: `micro_auth_then_larger`, `new_device`, `anonymous_proxy`, `region_never_seen`, `region_seen_and_home_continues`, `recurring_amount`, `shared_device_with_confirmed_case`, `structuring_under_500`, `history_consistent`.

`p = 1 / (1 + exp(-log_odds))`.

Memory enters as `prior_from_memory` when the closed cases in the same device or community have a measured confirm rate. The claim says so. Those case ids go to `similar_prior_cases`. Their verdicts are not appended as if this card had been seen doing the fraud.

Independent evidence, for the stop rule, means different measurement families: amount-sequence, device, region, recurring history, prior-case link, customer reply. Two rows from the same query count as one. The risk score counts as one only as the prior, and it cannot be the second piece.

Contradiction flag: a strong fraud finding together with a strong legitimate finding (recurring match and a shared-device confirmed case, or customer confirm against a testing sequence). R8 reads this flag.

### 4. Policy

Pure function. No model call. Unit-tested. Order is the stress test: the first matching mandatory rule wins, later rules can add actions, no later rule can remove a prohibition.

1. **R7 first** when the trigger is a dispute and `recurring_match` hits. Actions: `CREATE_CASE`, `VERIFY_WITH_CUSTOMER`, `WARN_CUSTOMER`. Block is forbidden even after the reply.
2. **R5** when the testing sequence is present. `DECLINE_TRANSACTION` and `STEP_UP_AUTH`. If a purchase over $100 has already cleared, add `BLOCK_CARD`.
3. **R9** when the pattern is `undocumented` and more than one customer is in the episode (proxy ring or structuring described in the closed notes). `CREATE_CASE`, `FILE_REPORT`, `ESCALATE_TO_ANALYST`. `pattern_description` is required. Do not relabel these as card-not-present.
4. **R6** when more than one card shows fraud (this episode or a confirmed closed case) from the same device, region cluster, or recipient email. `CREATE_CASE`, `FILE_REPORT`, `MONITOR_CONNECTED_CARDS`. Sharing a device with quiet cards is a second hop, not yet R6.
5. **R1** when the case is still a single signal and `p < 0.70`. `VERIFY_WITH_CUSTOMER` or `STEP_UP_AUTH` before any block. This is the cleared-case path. High `risk_score` alone stays here.
6. **R10** deletes `BLOCK_ALL_CARDS` unless two of this customer’s cards are confirmed fraud or credentials are confirmed compromised. The dataset has no credential-reset field. Do not invent one. `BLOCK_ALL_CARDS` stays off unless two of the customer’s own cards are in the episode or in confirmed closed cases.
7. **Open a case** whenever `p ≥ 0.30`, or an ask is being made, or the trigger is a dispute. That is README §3a. `CREATE_CASE` is `auto`.
8. **File a report** only when fraud is confirmed or strongly suspected (`p ≥ 0.85`, or a denial on top of a pattern, or R6, or R9) **and** one of: exposure > $1,000, shared device or region linked to other fraud, or R9. One predicate sets both the action and `sar.file`.
9. **Routes** from the table above, using exposure after the episode is frozen.
10. **Order** actions by what happens first: decline or verify, then block, then case, then report, then monitor, then escalate.

Pass 1 emits `initial` and either stops or records the ask. Pass 2 runs after the simulator:

- Confirm → **R3** `CLOSE_NO_FRAUD`, unless R7 already forbade treating this as a clean confirm. R7 keeps the case and the warning.
- Deny → **R2** `BLOCK_CARD` and `CREATE_CASE`, plus `FILE_REPORT` under the predicate in step 8. Route on exposure.
- No reply → **R4** `MONITOR_CARD` and `DECLINE_TRANSACTION`. `ESCALATE_TO_ANALYST` if exposure > $500.
- Verdict `uncertain` and (exposure > $500 or contradiction) → **R8** `ESCALATE_TO_ANALYST`.

Bayes minimum risk is used only when two legal actions remain and no rule orders them. The loss table is versioned. It cannot authorize a block R1 forbids, and it cannot drop a report R6 requires.

### 5. Reply simulator

No LLM. The assumption is a named rule, copied into `assumed_response`.

| Ledger | Ask | Assumed response | Policy pass |
| --- | --- | --- | --- |
| Recurring match on a dispute | `customer_validation` | Customer does not recognize the descriptor; history shows the same amount on a monthly spacing | R7 stands. No block |
| Single signal, region is in this card’s history, or several days in one new region while home activity continues | `customer_validation` | Customer confirms the purchase or the trip | R3 |
| Single signal, device `New`, no proxy, no other cards, amounts in this card’s usual range | `customer_validation` | Customer confirms a new phone | R3 |
| Testing sequence, structuring, anonymous-proxy multi-card profile, or device shared with a confirmed case | `customer_validation` only if R1 still requires it | Customer denies and still has the card | R2 |
| Nothing above, and `p` between 0.15 and 0.85 | `customer_validation` | No reply within 24 hours | R4, and R8 if exposure > $500 |
| Stop rule already met with two independent pieces | none | — | `final` equals `initial`, `what_changed` is `nothing` |

Card testing “confirmed by the sequence itself” does not need a denial to be real. If `p` and the evidence count already meet the stop rule, do not ask. Asking when the sequence is already decisive is the failure mode the stopping section marks down.

### 6. Stop

Stop when any of these is true, and write that sentence into `stop_reason`:

- `p ≥ 0.85` or `p ≤ 0.15`, and at least two independent evidence families
- the verification reply settles the question (confirm, deny, or the R7 history finding)
- the value of every remaining ask is below its cost, including the case where pass 2 already consumed the one allowed customer ask

A second customer ask is a harness error.

### 7. Language

The strong model writes `summary` (two to six sentences) and, only if `sar.file`, the narrative (six to twelve sentences: who, what, when, where, how, why). The prompt contains the ledger, the rule ids, the episode ids, and nothing else.

Jev `claim_supported` runs per sentence against the cited evidence. A failed sentence is dropped or rewritten once. If it still fails, the sentence is replaced by the evidence claim itself. The model cannot change `p`, the pattern, the ids, or the actions.

`pattern_description` for `undocumented` is two or three sentences from the measurement claims (device string, customer count, or the under-$500 spacing). It is assembled from the ledger, not invented.

### 8. Memory write

Vertex `ClosedCase` (or `InvestigationCase` if we do not want to mix exam rows into the historical file’s type — prefer a distinct type `ExamCase` with the same edges, so October calibration is not contaminated). Edges: `INVOLVES` transactions, `ON_CARD` the primary card, `CONNECTED_TO` the other cards, and a link to the device profile.

`written_to_graph` is set true only after `get_case(graph_case_id)` returns the same verdict and exposure. `graph_case_id` is `EXAM-<case_id>`, which does not collide with `CC-` ids.

The next exam case may retrieve an earlier exam case only through that edge. HHG-014’s ring should become visible to a later case that shares the device. Run the twenty in case-id order so that memory has a direction.

### 9. Answer builder

One module projects the case state onto the schema. It does not think. Tests:

- every required key present
- `pattern` in the seven-value enum
- `sar.file` matches `FILE_REPORT` in `final`
- legitimate ⇒ empty `affected_txn_ids`, exposure 0, `sar.file` false
- every txn, card, and `CC-` id exists in the dataset
- every action name and route is in the policy tables, and the route matches exposure
- `initial` is unchanged after the reply is applied
- `pattern_description` non-empty iff pattern is `undocumented`
- `written_to_graph` implies a non-empty `graph_case_id`

## Deployment

```text
Savanna workspace (auto-stop on)
  schema + installed queries + vector index of policy, patterns, closed-case notes
  MCP server pointed at that graph
        │
Python service
  harness (LangGraph checkpoint, sqlite)
  planes above
  POST /cases/{id}/run
  GET  /cases/{id}          the answer JSON
  GET  /cases/{id}/graph    the read-back vertex
        │
UI
  case list of the 20
  timeline of evidence
  p, pattern, independent-evidence count
  initial actions | final actions, with route badges
  SAR if filed
  stop reason
```

Local graph client implements the same query names for tests. The exam command refuses to start unless MCP health and a read-back both succeed. A green local run is not the submission.

Instrumentation on every case: `tool_calls`, `tokens`, `latency_s`. These fields are in the schema and will be empty if nobody counts them.

## What the demo shows

Four cases, three to five minutes, in this order, because they exercise different planes:

1. A high score that the measurements treat as a single signal. Initial action is verify. Assumed confirm. Final action is `CLOSE_NO_FRAUD`. This is the cleared-case path. Say out loud that the score was not the verdict.
2. A dispute whose amount repeats monthly. R7. Warn, do not block. `final` does not grow a `BLOCK_CARD`.
3. A case that grows a device or a testing sequence. Initial verify or decline. After the simulated denial, block, case, and a report only if the filing predicate is true. Show the approval badge: L1 or L2 from exposure, not from the model.
4. HHG-014, the analyst request. Second hop across the device. If it is the shared unusual profile, pattern `undocumented`, description in our words, report, escalate. Show the case vertex in TigerGraph and a prior `CC-` id in `similar_prior_cases`.

Then open `cases/HHG-014.json` so the file and the screen are the same object.

## Submission checklist

| Required | Where it comes from |
| --- | --- |
| Working agent | the service above, MCP connected, exam command |
| GitHub repo | this layout, dataset not rewritten, no Kaggle labels |
| 20 answer files | `cases/HHG-001.json` … `cases/HHG-020.json` |
| Case written to the graph | read-back, `written_to_graph: true` |
| SAR when policy says so | same predicate as `FILE_REPORT` |
| NBA before and after, with route | `initial`, `final`, `what_changed` |
| 3–5 minute video | the four beats |
| Blog | what we built, architecture, TigerGraph, agentic behavior, what we learned, what we would do with more time |
| Social post | tag @TigerGraphDB, link the blog or the video |

## Build order

1. Policy function and answer schema tests, using fixture ledgers. No graph yet. This locks R1–R10, routes, SAR agreement, and legitimate empties.
2. Load Customer, Card, Transaction, DeviceProfile, EmailDomain, BillingRegion, ClosedCase. Prove the measurement pack by hand on one closed confirmed case and one closed cleared case.
3. Belief tables from July–September. Print October calibration and stop. Do not open the exam file.
4. Wire pass 1, simulator, pass 2, stop, answer builder. Run one exam case. Diff the JSON against the schema test.
5. Graph write and read-back. Set `written_to_graph` from the read-back only.
6. Run all twenty in order. Human-read the eight customer reports and HHG-014 before trusting them.
7. UI on those four demo cases. Record only after a case on screen matches its JSON.
8. Blog and post from the architecture that actually ran, including the October calibration number and one thing the agent got wrong.

## What we will not claim

The probability is a calibrated estimate from closed months, checked on October, not a label from the public IEEE file. Jev does not approve blocks. The simulated customer is a named rule, written in the file, because the dataset does not contain replies. Undocumented means we refused a known pattern name, not that we found a mystery.

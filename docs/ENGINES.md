# Engines

One case moves through these engines in order. An engine receives one object and emits the next. It does not reach back and redo another engine’s job. LangGraph only checkpoints between them.

Offline engines run once, before `HHG-001`. The case engines run once per exam case, in case-id order, so a later case can see an earlier one in the graph.

```mermaid
flowchart TB
  subgraph OFF["Offline · once, before the exam"]
    direction LR
    CC["Closed cases Jul to Sep"] --> CAL["Calibration engine"]
    OCT["October closed cases"] --> CAL
    RAW["Full graph"] --> COM["Community engine"]
    DOCS["Policy, patterns, case notes"] --> VEC["Vector engine"]
  end

  CAL --> BEL
  COM --> HOP
  VEC --> HOP

  subgraph RUN["One case · checkpoint after every engine"]
    direction TB
    ROW["case_pack row"] --> IN["Intake engine"]
    IN --> PACK["Graph engine · measurement pack"]
    PACK --> BEL["Belief engine"]
    BEL --> PAT{"Pattern engine · hard hit?"}
    PAT -->|testing, region, structuring, recurring| LOCK["Pattern locked by the measurement"]
    PAT -->|no hard pattern| JEV1["Control engine · Jev picks known, undocumented, or insufficient"]
    LOCK --> HOPQ{"Control engine · Jev · one more hop?"}
    JEV1 --> HOPQ
    HOPQ -->|yes, once| HOP["Graph engine · second hop"]
    HOP --> BEL
    HOPQ -->|no, or hop already used| POL1["Policy engine · pass 1"]
    POL1 --> ASK{"Reply engine · must we ask?"}
    ASK -->|stop rule already true| SAME["final actions = initial actions"]
    ASK -->|ask once| SIM["Reply engine · named assumption"]
    SIM --> BEL2["Belief engine · reply likelihood"]
    BEL2 --> POL2["Policy engine · pass 2"]
    SAME --> STOP["Stop engine"]
    POL2 --> STOP
    STOP --> WRITE["Language engine"]
    WRITE --> SENT{"Control engine · Jev · sentence has a ledger id?"}
    SENT -->|rewrite once| WRITE
    SENT -->|yes| MEM["Memory engine"]
    MEM --> OUT["Answer engine"]
  end
```

## What crosses each arrow

| From | To | The object |
| --- | --- | --- |
| Calibration | Belief | Frozen map from risk score to probability, plus a likelihood ratio per finding |
| Community | Second hop | Louvain id and FastRP vector already stored on the card |
| Vector | Second hop | Policy paragraph and old-case notes, only if that hop is chosen |
| Intake | Measurement pack | `trigger_type`, transaction id, card id, customer id |
| Measurement pack | Belief | Claims with real ids: window, device, region, monthly repeat, old cases |
| Belief | Pattern | `p`, which evidence families fired, contradiction flag |
| Pattern | Hop question | One of the seven pattern names, locked by code when a hard detector fired |
| Second hop | Belief | New claims only. Belief adds their likelihood ratios. It does not restart the case |
| Policy pass 1 | Reply | `initial` actions, routes, and whether a customer ask is still legal |
| Reply | Belief | One assumption: confirm, deny, no reply, or monthly-charge dispute |
| Policy pass 2 | Stop | `final` actions. `FILE_REPORT` and `sar.file` are the same bit |
| Stop | Language | `stop_reason` plus the ledger. The writer does not get the raw CSVs |
| Language | Jev | Draft sentences, each tied to one evidence `ref` |
| Memory | Answer | The case vertex read back from TigerGraph. `written_to_graph` is set here |
| Answer | `cases/HHG-xxx.json` | Schema only. This engine does not think |

## What each engine is allowed to decide

| Engine | Decides | Does not decide |
| --- | --- | --- |
| Calibration | How much a bank score and a finding should move `p` | Any exam case. October is the check, then the table is frozen |
| Community | Which cards sit together, computed once | Whether this charge is fraud |
| Vector | Which policy sentence to show the writer | The action |
| Intake | Nothing. It types the alert | The verdict |
| Graph | Facts: counts, ids, times, device string | Block, report, or pattern name |
| Belief | `p` from the frozen ratios | The action. An old case can move the prior only |
| Pattern | The enum. Hard detectors beat Jev | The block. Recurring match locks the R7 path |
| Jev | Second hop or not. Unnamed pattern when nothing hard fired. Whether a sentence is supported | `BLOCK_CARD`, the probability, the ids |
| Policy | Actions, approval route, report yes or no, in R1–R10 order | A new fact |
| Reply | The assumed customer line, from the ledger | A free-text story |
| Stop | The sentence in `stop_reason` | A new action |
| Language | Wording of the summary and the report | Numbers and ids |
| Memory | That the vertex matches the case we just built | A nicer verdict on the way out |
| Answer | That the JSON matches the README | Anything else |
| LangGraph | Resume after a crash. One ask. One hop. One rewrite | Every row above |

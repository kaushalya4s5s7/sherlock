# Coding rules

This file is the law for code in this repo. Read it before adding a package, a dependency, or a shortcut.

Spec order, when documents disagree:

1. `HHGOA_IEEE 2/README.md` — the graded contract. `docs/challenge.md` is the hackathon wrapper. Do not invent a second spec.
2. `docs/ARCHITECTURE.md` — engines, rule order, reply rules, stop rule.
3. `docs/INNOVATION.md` — the extra outputs that must exist, and the things we will not add.
4. `docs/ENGINES.md` — what object crosses each boundary.
5. This file — how the code is allowed to be shaped.

The product is twenty valid answer files, twenty case vertices read back from TigerGraph, and a screen that shows one investigation from trigger to approval. A clever abstraction that does not produce those is a failed change.

## Stack

The required stack is the one the brief names, plus the smallest runtime that can host the engines.

| Capability | Public package | Private implementation | Why |
| --- | --- | --- | --- |
| Graph facts | `graph` | TigerGraph via MCP. A local adapter with the same queries for tests | The brief requires TigerGraph, GSQL, and MCP |
| Control gates | `control` | Jev, pinned version. A deterministic fallback if the API is down | Typed yes/no and choice. Not a writer |
| Case flow | `harness` | LangGraph checkpoints | Resume, one hop, one ask, one rewrite |
| Prose | `language` | One strong chat model behind an adapter | Summary and SAR only |
| HTTP | `apps/api` | FastAPI | Thin. No rules in routes |
| Screen | `apps/dashboard` | Vite + React | Talks only to the API |
| Contracts | `contracts` | Pydantic v2 | One schema for the answer file, the ledger, and the API |
| Tests | pytest | — | Public behavior, not private classes |

Python 3.12. `uv` workspace. Do not split the agent into a TypeScript monorepo. The principles below are the universal architecture; the language is Python because MCP, GSQL, and LangGraph live here. The dashboard is the only TypeScript app, and it never imports a Python package.

Do not add a second agent framework, a queue, a vector database beside TigerGraph, or a graph neural net.

## Package types

Name a package by the capability, never by the vendor.

Correct: `graph`, `control`, `language`, `memory`.

Wrong: `tigergraph`, `jev`, `openai`, `langgraph` as a package other code imports.

Vendor code sits in `private/`.

### Service packages

```text
packages/
  contracts/      shared schemas only. No I/O
  intake/
  graph/
  belief/
  pattern/
  control/
  policy/
  reply/
  stop/
  language/
  memory/
  answer/
  harness/
  calibration/    offline. Never imports the exam pack
  community/      offline Louvain and FastRP
```

### Applications

```text
apps/
  api/            deployable HTTP
  dashboard/      deployable UI
```

Applications may depend on packages. Packages must not import an application. Applications must not import each other.

### Configuration

```text
tooling/          ruff, pytest, tsconfig. No business logic
gsql/             schema and installed queries. Not imported as Python
```

`HHGOA_IEEE 2/` is read-only input. Code never writes into it. Generated output is `cases/` and, only after the twenty files pass, `extra/`.

## Dependency direction

```text
apps/dashboard  →  HTTP only  →  apps/api
apps/api        →  harness
harness         →  intake, graph, belief, pattern, control, policy, reply, stop, language, memory, answer
memory          →  graph, contracts
language        →  contracts
control         →  contracts
graph           →  contracts
belief, pattern, policy, reply, stop, answer, intake  →  contracts only
calibration, community  →  contracts, and files under HHGOA_IEEE 2 except case_pack.csv
```

Forbidden:

- `policy` importing `control`, `language`, or `graph`
- `reply` importing `language` or `control`
- `language` changing `p`, pattern, ids, or actions
- `control` emitting an action name
- `belief` importing `case_pack.csv` or any `HHG-` file
- `dashboard` importing a service package
- any cycle
- any import of `private/`

If a package needs something from another package's `private/`, promote a function onto that package's public API. Do not bypass the boundary.

## Inside a service package

```text
packages/<capability>/
  public/
    __init__.py      the only import path
    types.py
    service.py
  private/
    providers/       vendor SDKs and HTTP clients
    repositories/
    adapters/
  tests/
```

Consumers import `packages.graph` (or the workspace name `graph`) and call `graph.measurement_pack(card_id, txn_id)`. They do not construct a TigerGraph client, a Jev client, or an LLM client.

Prefer a configured instance when the service can read its own env (`graph`, `control`, `language`). Use a factory only when tests must inject the local graph adapter or a fake control client. Do not add a factory for style.

## What each public function is allowed to do

The harness is the only orchestrator. Engines are functions over data.

| Package | Public function | Input | Output | I/O |
| --- | --- | --- | --- | --- |
| `intake` | `open_case` | one case-pack row | typed trigger | Read the row only |
| `graph` | `measurement_pack` | card, txn, as-of time | ledger claims | TigerGraph or local adapter |
| `graph` | `second_hop` | hop name from control | more claims, or empty | Same |
| `belief` | `update` | ledger + frozen tables | `p`, families, contradiction, LR list | None |
| `pattern` | `classify` | ledger | pattern enum, `why_not` for the five that lost, lock bit | None. A hard detector sets the lock. The harness may call `control` only when the lock is false, then pass that label back in |
| `control` | `hop`, `pattern_gate`, `sentences` | a short state, not the raw case | full probability map, not only the winner | Jev, or the fallback |
| `policy` | `decide` | belief, pattern, ledger, reply phase | actions, routes, rule register, ask flag | None |
| `reply` | `assume` | ledger + ask flag | one evidence request, or none | None |
| `stop` | `commit` | belief, reply, policy output | `stop_reason`, point of commitment | None. Replays `policy.decide` with one family removed |
| `language` | `draft` | ledger, actions, rule ids | summary and SAR text | LLM, or claim-concatenation fallback |
| `memory` | `write_and_read` | final case | `graph_case_id` only after read-back matches | Graph |
| `answer` | `build` | the objects above | JSON that validates, or a list of errors | None |
| `harness` | `run` | case id | answer file path | Checkpoints |

`policy.decide` is called twice. Pass 1 has no reply. Pass 2 has the assumption. `initial` is the pass-1 list and must be unchanged after pass 2.

Innovation outputs are part of the public result, not optional logs:

- Rule register: all of R1–R10, each `fired` or `not_fired`, one line why.
- Point of commitment: the evidence family whose removal changes the final actions.
- Counterfactuals: action lists for the replies we did not assume, labeled `not what happened`.
- `why_not`: why each named pattern lost, when pattern is `undocumented` or `none`.

## Business rules that code must not "simplify"

These are graded. A refactor that drops one of them is a bug.

- A customer report is a dispute, not a denial. R7 runs before R2.
- R1: one signal and `p < 0.70` means verify or step-up before any block.
- R5 always has data, because `measurement_pack` always runs the card window.
- R6 needs fraud on the other cards, not merely a shared device.
- R9 stays `undocumented`. Do not relabel the Samsung-proxy cluster or the under-$500 cluster as card-not-present.
- R10: `BLOCK_ALL_CARDS` stays off unless two of this customer's cards are confirmed. There is no credential-theft column. Do not invent one.
- `FILE_REPORT` and `sar.file` are set in one place inside `policy`.
- Legitimate verdict: `affected_txn_ids` empty, exposure 0, `sar.file` false.
- `uncertain` is a legal verdict. Pair it with R1 or R8, not with a block.
- Exposure is the sum of absolute amounts of the episode transactions, in USD, rounded to cents.
- Every id in the answer exists in the dataset. The README example ids (`T0412877`, `C00377`) are illustrations. Reject them.
- `similar_prior_cases` may contain `CC-` ids and, after a previous exam case was read back, `EXAM-HHG-` ids. Run the exam in case-id order.
- `written_to_graph` is true only when `memory.write_and_read` returns a vertex with the same verdict and exposure.
- Do not open the public IEEE-CIS or Kaggle files. Do not fit tables on `HHG-001`–`HHG-020`.
- Calibration uses July–September. October is a check, then the table file is frozen. `calibration` cannot read `case_pack.csv`.

Action names and routes are the README tables. No synonyms.

## Thin transport

`apps/api` routes do this and nothing else:

```text
receive → validate with contracts → harness.run or a read → return JSON
```

A route does not compute exposure, pick a rule, or call Jev. Approval is `POST /cases/{id}/approve` with the case id and the action. The handler asks `harness` to resume. It does not set `BLOCK_CARD` itself.

The dashboard renders the case the API returns: timeline, LR waterfall, rule register, initial actions, final actions, counterfactuals, point of commitment, SAR, approval button. It does not reimplement R1–R10 in JavaScript.

## Vendor isolation

| Need | Call this | Never call this from an engine |
| --- | --- | --- |
| A fact about a card | `graph.measurement_pack` | `pyTigerGraph`, raw GSQL, MCP tool objects |
| A gate | `control.hop` / `pattern_gate` / `sentences` | the Jev HTTP API |
| A paragraph | `language.draft` | an OpenAI or Anthropic client |
| A saved case | `memory.write_and_read` | a RESTPP URL |

GSQL strings live in `gsql/` and in `graph/private`. The measurement pack calls installed query names. The agent does not generate GSQL at runtime.

## Environment

Each package that needs a secret owns a `public/keys.py` validated at process start. Missing config fails the process. Do not sprinkle `os.environ` through engines.

Required for an exam run: TigerGraph host, graph name, token, Jev API key and pinned model version, language-model key. The exam command checks MCP health and a read-back before the first case. A local-adapter run may produce JSON for tests. It must refuse to set `written_to_graph` or to write into `cases/` as the submission.

Startup prints which adapter is live: `tigergraph` or `local`, and the pinned Jev version. A silent fallback during the submission run is a bug. Fallbacks are allowed only when the command was started with `--allow-fallback`, and the answer file records that in `stop_reason` or a warning field inside the summary. The submission run does not pass `--allow-fallback`.

## Failure behavior

Handle these in the package that owns them. Do not catch-and-continue in the harness with an empty case.

| Failure | Owner | Behavior |
| --- | --- | --- |
| TigerGraph down on the exam command | `graph` | Raise. The run stops. Do not write a partial answer file |
| Query timeout or error | `graph` | One retry. Then a claim with source `graph`, the error in `ref`, empty `entity_ids`. Not fraud, and not "clean" |
| In-person transaction, no identity row | `graph` | Empty device claim. Continue |
| Empty neighbor list | `graph` | A real claim: "no other card on this device" |
| Jev timeout or HTTP error | `control` | Fallback: hop = `none`, pattern gate = `insufficient`, sentence check = keep only sentences that quote an evidence claim. Record the fallback on the case |
| Choice split, top two options within 0.1 | `control` | Do not treat that as "unknown." Store both. Pattern gate: if a hard detector did not lock, leave the label `insufficient` and list both options in `why_not`. Hop: take `none`. A flat distribution is not a block and not a pattern |
| Language model timeout | `language` | Summary becomes the evidence claims joined. SAR narrative, if required, becomes those claims in who/what/when order. No new facts |
| Sentence rejected twice | `harness` | Replace that sentence with the evidence claim. Do not loop |
| Write succeeds, read-back mismatches | `memory` | `written_to_graph` false. `run` fails the case. Do not emit a submission file |
| Same case run twice | `memory` | Upsert `EXAM-<case_id>`. Do not create a second vertex |
| Process crash | `harness` | Resume from the last checkpoint. Do not send a second ask or a second hop |
| `L1` or `L2` action | `harness` | Park the run. Auto actions may be marked executed. The block, decline, or report stays `pending_approval` until the approve call |
| Approve for an action not in `final` | `harness` | Reject. Do not add the action |
| NaN or infinite `p` | `belief` | Clamp with the floored LR. If inputs are missing, `p` stays the prior and the case is `uncertain` |
| Unknown id in a claim | `answer` | Validation error. The file is not written |
| `sar.file` disagrees with `FILE_REPORT` | `answer` | Validation error |
| Clock | every package | Use `ts` from the row. Do not use `datetime.now()` to decide fraud |

Retries are one, with the error stored. No retry loops inside an engine.

## Testing

Test the public function, with a fixture ledger, not the private client.

Must exist before the exam run:

- `policy`: one test per rule R1–R10, including R7 before R2, R10 blocking `BLOCK_ALL_CARDS`, report predicate on and off, route by exposure at $2,500 and $2,500.01.
- `reply`: each row of the assumption table. No test may call a model.
- `answer`: legitimate empties, undocumented description required, fake README ids rejected, `initial` unchanged after pass 2.
- `stop`: removing the committed family changes the action; removing another family does not.
- `belief`: a known LR moves `p` in the expected direction; a prior-case id does not enter the ledger as proof.
- `graph` local adapter: one confirmed closed case and one cleared closed case return the expected claim types.
- `harness`: crash after pass 1 resumes without a second ask.
- `memory`: read-back mismatch refuses the flag.

Do not snapshot the entire 590k CSV in a unit test. The exam command is the integration test, and it runs last.

## Before a new package or dependency

Ask:

1. Is this a capability we already have?
2. Does the README grade it?
3. Does the import arrow point toward `contracts`, never toward `apps`?
4. Is the name a capability?
5. Can the exam run finish if this dependency is slow?

No package for "utils". Shared types go in `contracts`. Duplicating a ten-line mapper is better than a dependency cycle.

## What "done" means for a change

A change is done when:

- the public tests for the package pass
- no engine gained a second job
- an answer file for one closed-case fixture still validates
- the dashboard, if touched, shows data from the API and does not compute a rule

The exam command is done when `cases/HHG-001.json` through `cases/HHG-020.json` validate, each `written_to_graph` is true, and the dashboard can open HHG-014, show the rule register, the point of commitment, and an L2 approval that resumes the run.

Build in that order. Do not start the dashboard before one JSON validates. Do not start `extra/` before the twenty files validate.

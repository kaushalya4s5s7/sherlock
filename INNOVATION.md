# Where to innovate

Innovation is 15% of the score. The README also gives one free point: if the agent watches the exam months on its own and investigates past the 20 cases, put those in a separate folder. That counts as innovation, not accuracy. Do it only after the 20 files exist.

The other teams will show a graph, a policy table, and a paragraph. A new model in the middle of that is not visible. An engine that already has one job can grow one trick a judge can point at.

Fall 2026 YC requests that match this pipeline: [Multiplayer AI](https://www.ycombinator.com/rfs) (a teammate can enter a live agent run, redirect it, and take it over), [AI-native compliance](https://www.ycombinator.com/rfs) (obligations, controls, and an audit trail, not a chatbot that "does compliance"), and the summer request [Software for agents](https://modelence.com/yc-rfs-summer-2026/software-for-agents) (replay, an approval gate, a warning before an irreversible act). The paper that fits the policy engine is [Causal Agent Replay](https://arxiv.org/abs/2606.08275): the step that matters is the one where changing it changes the outcome. Their LLM-judge baseline for "which step caused this" is about 14%. We do not need their Monte Carlo sampler. Our policy function is deterministic, so one replay per evidence family is the whole experiment.

## Per engine

| Engine | Innovate? | The move |
| --- | --- | --- |
| Calibration | Small | Show the October check on the case page: "when we said 0.8 on October, we were right this often." The honesty of `p` is already graded. A chart makes it visible |
| Community | Yes, offline | Louvain once. If a card's community matches the Samsung-proxy cluster or the under-$500 cluster in the nine `undocumented` closed cases, the pattern engine must say `undocumented` and describe it. Forcing those into "card not present" is how the other teams will miss the scored pattern |
| Vector | No | Retrieve the policy paragraph that fired. Do not retrieve more text to sound smart |
| Intake | No | Three trigger types. That is the whole job |
| Graph pack | No | Same seven checks every case. Skipping one is how innovation breaks R5 |
| Belief | Small | Draw the likelihood ratios as a waterfall: score prior, then device, then region. Old cases move only the prior |
| Pattern | Yes | Hard detectors lock the name. Jev speaks only when they miss. The output includes `why_not` for the five named patterns that lost |
| Jev | Already the innovation | Keep it on three gates: second hop, unnamed pattern, sentence check. Giving it the block button erases the innovation and the policy |
| Policy | Yes | Emit a register of all ten rules, each `fired` or `not fired`, with one line why. Cite the winner and show the losers. YC's compliance request is this register, not a longer SAR |
| Reply | Yes | Next to the assumed reply, run the policy on the other two replies and show those action lists as counterfactuals. Label them `not what happened` |
| Stop | Yes | Name the evidence family that the action depends on. Drop each family, rerun policy, and record the first drop that changes the action. That family is the point of commitment from Causal Agent Replay, computed in milliseconds because the policy is pure code |
| Language | No | It writes. Jev already checks the sentences |
| Memory | Yes, if the data allows | Run the 20 in order. If a later case shares a device with an earlier exam case, `similar_prior_cases` includes `EXAM-HHG-…`. That is the brief's "use past investigations," shown live |
| Answer | No | Schema and real ids. A clever JSON loses |
| Harness | Yes, and it is the demo | This is the multiplayer request. The run pauses on `L1` or `L2`. A second person opens the same case, sees the register and the point of commitment, approves or sends it back. The agent does not continue on an unapproved block. One approval in the video is enough |

## What to build, in order

1. The rule register on policy pass 1 and pass 2. It falls out of the rules function. Put it in the case JSON under evidence or summary, and on the screen.
2. The point of commitment. Ten replays of the policy function with one evidence family removed. One sentence: "the block depends on the shared device; without it the action is verify."
3. The other-reply counterfactuals, marked as not taken.
4. The pause for a human on `L2`, then continue. Film that.
5. If the 20 files are valid, a separate folder of extra alerts from November and December risk scores. The README scores this as innovation.

## What not to add

A second analyst agent, a graph neural net choosing `BLOCK_CARD`. Two humans steering one run need an owner: the policy engine owns the action, the human owns approval, the agent owns the facts. A shared screen with no owner is the failure mode inside the multiplayer idea itself.

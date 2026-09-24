from graph import load_index
from harness import run

idx = load_index()
for case in idx.pack:
    result = run(case, idx)
    answer = result["answer"]
    final = ",".join(x["action"] for x in answer["next_best_actions"]["final"])
    initial = ",".join(x["action"] for x in answer["next_best_actions"]["initial"])
    print(
        f"{case['case_id']} {case['trigger_type'][:12]:12} p={answer['case']['fraud_probability']:.2f} "
        f"{answer['case']['verdict'][:11]:11} {answer['case']['pattern']}"
    )
    print(f"   init {initial}")
    print(f"   fin  {final}")
    print(f"   {answer['case']['pattern_description'][:140]}")

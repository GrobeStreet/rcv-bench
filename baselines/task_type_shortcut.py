#!/usr/bin/env python3
"""Baseline D: 'task-type shortcut' (structural tell exploiter).

Reads only claim.json and performs NO verification of any kind. It exploits a
structural regularity in the sanitized task packet:

    task_type == "ROBUST"  <=>  a "perturbation" block is present
                           <=>  gold verdict is FRAGILE   (3/3 in v1)

Because those three facts are perfectly aligned in the v1 corpus, a policy that
simply maps ROBUST -> FRAGILE scores full FRAGILE recall -- the metric on which
the naive-rerun baseline scores 0/3 -- without regenerating a single value or
probing a single perturbation.

This baseline exists so that number is published rather than available. Any
agent reporting FRAGILE recall on RCV-Bench v1 must beat this floor before the
result can be read as robustness-checking capability.

Scope: the alignment holds over three instances, and this policy's verdict
accuracy (0.571) remains below naive-rerun (0.643). The claim is narrow -- that
FRAGILE recall is uninformative on v1 -- not that this policy is good.

Note that withholding `task_type` alone would not close the channel, since the
presence of the `perturbation` block carries the same signal. Closing it
properly requires v2 instances whose declared perturbation HOLDS (gold ROBUST),
so that the ROBUST task type stops being a one-to-one tell.
"""
import json, glob, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def predict(claim):
    structural_robustness_task = (
        claim.get("task_type") == "ROBUST" or bool(claim.get("perturbation"))
    )
    verdict = "FRAGILE" if structural_robustness_task else "REPRODUCED"
    return {
        "claim_id": claim["claim_id"],
        "verdict": verdict,
        "localized_cause": "none",
        "confidence": 0.5,
        "escalate": False,
        "evidence": ["structural task_type/perturbation tell; no verification performed"],
    }


def main():
    preds = []
    for cj in sorted(glob.glob(os.path.join(ROOT, "tasks", "*", "claim.json"))):
        preds.append(predict(json.load(open(cj))))
    out = os.path.join(ROOT, "baselines", "predictions_task_type_shortcut.json")
    json.dump(preds, open(out, "w"), indent=2)
    print(f"wrote {len(preds)} predictions -> {out}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Baseline B: 'naive-rerun'. Models a competent-but-shallow agent that RE-RUNS the
headline number and compares it to the claim, but (1) never applies the declared
perturbation on ROBUST tasks, and (2) cannot tell fabrication from a plain deviation.

Policy (reads claim.json + harness/rerun_observations.json; NEVER reads GOLD/):
  - task_type == ROBUST            -> REPRODUCED   (it never perturbs, so the full-data
                                                    number matches and it declares success)
  - REPRO & headline matches claim -> REPRODUCED
  - REPRO & headline mismatches     -> DEVIATION    (labels ALL mismatches DEVIATION;
                                                    never emits FABRICATED)
This is deliberately the naive blind spot the benchmark exists to expose."""
import json, glob, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OBS = json.load(open(os.path.join(ROOT, "harness", "rerun_observations.json")))["observations"]

def predict(claim):
    cid = claim["claim_id"]
    if claim.get("task_type") == "ROBUST":
        return {"claim_id": cid, "verdict": "REPRODUCED", "localized_cause": "none",
                "confidence": 0.65, "escalate": False,
                "note": "ran full-data entrypoint only; no perturbation applied"}
    matches = OBS[cid]["matches_claim"]
    if matches:
        return {"claim_id": cid, "verdict": "REPRODUCED", "localized_cause": "none",
                "confidence": 0.75, "escalate": False}
    return {"claim_id": cid, "verdict": "DEVIATION", "localized_cause": "value-mismatch",
            "confidence": 0.60, "escalate": False,
            "note": "recomputed headline != claim; naive cannot localize cause or detect fabrication"}

def main():
    preds = [predict(json.load(open(cj)))
             for cj in sorted(glob.glob(os.path.join(ROOT, "tasks", "*", "claim.json")))]
    out = os.path.join(ROOT, "baselines", "predictions_naive_rerun.json")
    json.dump(preds, open(out, "w"), indent=2)
    print(f"wrote {len(preds)} predictions -> {out}")

if __name__ == "__main__":
    main()

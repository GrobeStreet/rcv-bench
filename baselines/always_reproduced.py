#!/usr/bin/env python3
"""Baseline A: 'always-REPRODUCED' (rubber stamp). Reads only claim.json; trusts every
claim. Establishes the floor: it can only be right on genuinely-reproduced instances."""
import json, glob, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def predict(claim):
    return {"claim_id": claim["claim_id"], "verdict": "REPRODUCED",
            "localized_cause": "none", "confidence": 0.5, "escalate": False}

def main():
    preds = []
    for cj in sorted(glob.glob(os.path.join(ROOT, "tasks", "*", "claim.json"))):
        preds.append(predict(json.load(open(cj))))
    out = os.path.join(ROOT, "baselines", "predictions_always_reproduced.json")
    json.dump(preds, open(out, "w"), indent=2)
    print(f"wrote {len(preds)} predictions -> {out}")

if __name__ == "__main__":
    main()

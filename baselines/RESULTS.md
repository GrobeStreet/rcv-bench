# RCV-Bench v0 — reference baselines & headroom (2026-08-25)

Two deterministic reference policies scored against the 14 held-out gold verdicts.
They are **policies, not live LLM agents** — they exist to prove the scorer end-to-end
and to establish how far a shallow strategy gets, so a real agent has a number to beat.

| Baseline | Verdict acc | macro-F1 | FRAGILE recall | FABRICATED recall | Brier |
|---|---:|---:|---:|---:|---:|
| always-REPRODUCED (rubber stamp) | 0.357 (5/14) | 0.132 | 0/3 | 0/2 | 0.250 |
| naive-rerun (recompute headline, no perturbation) | 0.643 (9/14) | 0.392 | 0/3 | 0/2 | 0.210 |
| **perfect agent (ceiling)** | **1.000 (14/14)** | **1.000** | **3/3** | **2/2** | — |

## What the numbers say
- **naive-rerun solves the easy half.** It gets every REPRODUCED (5/5) and every DEVIATION
  (4/4) — including the tampered ledger, the FAIR sign-inversion bug, the ARC self-correction,
  and the MMLU calibration non-reproduction — because a straight re-run + compare catches
  a wrong number.
- **It is totally blind to the two hard classes.** FRAGILE recall **0/3** (it calls
  `ds-fragile-01`, `arc-leaderboard-01`, `mmlu-flip-01` REPRODUCED — it never deletes the
  tracer, never power-tests the leaderboard, never reorders the options) and FABRICATED
  recall **0/2** (it labels fabrication as plain DEVIATION — it can't tell "wrong number"
  from "invented result with no artifact").
- **That 5-instance / 35.7-point gap is the benchmark's reason to exist.** Closing it
  requires exactly the capabilities Snorkel's RFP asks for: probing robustness under a
  declared perturbation, and provenance/uncertainty reasoning beyond re-execution.

## Reproduce
```bash
python3 baselines/always_reproduced.py    # -> predictions_always_reproduced.json
python3 baselines/naive_rerun.py          # -> predictions_naive_rerun.json  (uses harness/rerun_observations.json)
python3 scoring/score.py baselines/predictions_naive_rerun.json --name naive-rerun
python3 scoring/score.py baselines/predictions_always_reproduced.json --name always-REPRODUCED
```
Neither baseline reads `GOLD/`. `harness/rerun_observations.json` holds only PUBLIC headline
recomputations (regenerated numbers / receipts), not verdict labels — the naive policy still
has to derive the verdict, and provably fails on fragility and fabrication.

## Scorer rubric (scoring/score.py)
verdict accuracy · macro-F1 over the 5 classes · per-class P/R/F1 · **FRAGILE & FABRICATED
recall** (the headroom classes) · localization accuracy on defect cases · escalation P/R ·
Brier calibration on confidence. This is the multi-factor rubric from the spec, not pass/fail.

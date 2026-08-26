# RCV-Bench — Research-Claim Verification Benchmark (v1 harness)

**Can an agent tell whether a claimed research result is real?** RCV-Bench scores an agent
on verifying or refuting a claimed numeric result given the claim + its code: regenerate the
number, catch a planted defect, stress-test robustness under a declared perturbation, and
surface calibrated uncertainty — verdicts, not vibes.

Built for the kind of evaluation gap the [Snorkel Open Benchmarks Grant for Agentic AI](https://benchmarks.snorkel.ai/)
targets: **output complexity** — multi-factor rubrics and *trustworthy outputs that surface
uncertainty and recognize escalation* — in a lane (research-claim verification) the funded
cohort doesn't cover. See [`SNORKEL-MAPPING.md`](SNORKEL-MAPPING.md).

## v1: real agent-under-test harness

RCV-Bench now has an external process protocol for real agents. `harness/run.py --command ...`
creates a sanitized per-task workspace with `claim.json`, `README.md`, and `env/` when present,
withholds `GOLD/`, sends the task JSON to the agent on stdin, validates its JSON verdict, records
runtime/errors, and writes a predictions file consumable by the existing scorer.

This is a **harness milestone, not a frontier-agent result**: no provider/model score is claimed
until an actual agent is run under a declared isolation, network, tool, model/version, and time
budget. See [`harness/AGENT_PROTOCOL.md`](harness/AGENT_PROTOCOL.md).

## Verdict classes
`REPRODUCED` · `DEVIATION` · `FABRICATED` · `ROBUST`→`FRAGILE`

An agent reads `claim.json`, follows the protocol (check out the pin, rebuild, regenerate the
headline, verify hashes/pin, apply any declared perturbation), and emits a verdict object:
```json
{ "verdict": "...", "regenerated_value": ..., "delta_vs_claim": ...,
  "localized_cause": "...", "confidence": 0.0-1.0, "escalate": false, "evidence": [...] }
```

## Benchmark corpus — 14 instances, 4 real repos
Every gold value is **regenerated in-sandbox** (11) or an **externally-verified receipt** (3, FAIR only).
Spread: REPRODUCED 5 · DEVIATION 4 · FRAGILE 3 · FABRICATED 2. Full table: [`tasks/README.md`](tasks/README.md).

| source repo | instances | example |
|---|---:|---|
| de-stress-lab (DESI DR2 cosmology) | 6 | headline 2.75σ time-variation collapses to 1.81σ when one tracer (LRG2) is deleted → **FRAGILE** |
| arc-agi-2-occam-baseline | 3 | earlier prefix analysis (50/87/95, +24pt) overturned by leakage-free same-holdout (32.8/50.8/63.4, +11.1) → **DEVIATION** |
| FAIR EXP-001 (weak-lensing, Codabench #10902) | 3 | OoD score sign-inversion scores 0.00457 below chance → **DEVIATION**; doctored 0.28 with no artifact → **FABRICATED** |
| mmlu-robustness-audit | 2 | MMLU accuracy flips on ~78% of questions under a semantically-null option reorder → **FRAGILE** |

## Headroom (reference baselines)
Two deterministic policies establish the floor a real agent must beat. Full write-up: [`baselines/RESULTS.md`](baselines/RESULTS.md).

| system | verdict acc | macro-F1 | FRAGILE recall | FABRICATED recall |
|---|---:|---:|---:|---:|
| always-REPRODUCED (rubber stamp) | 5/14 (0.357) | 0.132 | 0/3 | 0/2 |
| naive-rerun (recompute headline, no perturbation) | 9/14 (0.643) | 0.392 | 0/3 | 0/2 |
| **perfect agent (ceiling)** | **14/14 (1.000)** | **1.000** | **3/3** | **2/2** |

Re-running catches wrong numbers, so naive-rerun clears every REPRODUCED and DEVIATION — but
it is **blind to fragility (0/3)** and **fabrication (0/2)**. That 5-instance gap is what the
benchmark measures: robustness-probing and provenance reasoning that re-execution can't provide.

## Run it
```bash
# regenerate the task tree (deterministic)
python3 build_tasks.py

# score the reference baselines
python3 baselines/always_reproduced.py
python3 baselines/naive_rerun.py
python3 scoring/score.py baselines/predictions_naive_rerun.json --name naive-rerun

# v1 external-process smoke test (replace with a real agent adapter)
python3 harness/run.py \
  --command "python3 /absolute/path/to/rcv-bench/harness/example_external_agent.py" \
  --out predictions_external.json --trace trace.jsonl
python3 scoring/score.py predictions_external.json --name external-smoke-test

# independently regenerate any de-stress / arc gold value (the whole point):
#   see tasks/README.md "How to regenerate the gold"
```

## Layout
```
tasks/<id>/  claim.json (agent sees) · README.md · GOLD/gold.json (scorer only)
harness/     run.py · agent_protocol.py · AGENT_PROTOCOL.md · example_external_agent.py
             mmlu_live.py · rerun_observations.json
baselines/   always_reproduced.py · naive_rerun.py · RESULTS.md · predictions_*.json
scoring/     score.py   (macro-F1, per-class P/R/F1, FRAGILE/FABRICATED recall, localization, Brier)
build_tasks.py · SNORKEL-MAPPING.md · leaderboard/index.html
```

## Roadmap
- **v0 corpus:** 14 instances, gold regenerated/verified, 2 baselines, scorer. **Eleven run end-to-end in-sandbox** (incl. MMLU via `harness/mmlu_live.py`, an exact-match batched reproduction of the option-reorder audit); three (`fair-*`) are external-gated on the 8.7 GB FAIR dataset and score verdict logic now.
- **v1 harness (shipped):** external process boundary, sanitized task packets, strict verdict validation, timeout/error semantics, execution traces, and a provider-agnostic adapter contract.
- **next decisive result:** run one or more real agents under a declared isolation/tool/network budget and publish their scores; then add FAIR live execution and expand the task corpus.

## Provenance & honesty
Gold is regenerated, never copied from prose. Two discipline catches during the build are documented in the crew log: a source repo's README *summary* disagreed with its own manifest (we used the manifest), and a pre-written tampered-hash gold didn't match the actually-staged artifact (corrected to match reality). The `fair-*` and `arc-selfcorrect` instances use each source repo's own documented frozen-vs-regenerated records — real self-corrections, not invented ground truth.

The current public task corpus includes public gold for auditability. A publishable agent score therefore requires a run boundary that prevents the agent from reading the benchmark checkout or memorized/public gold; future held-out task packs should provide the stronger evaluation condition.

## License
Benchmark code: Apache-2.0. Task data & gold: CC BY 4.0. Source repos used as instances are
MIT (de-stress-lab, mmlu-robustness-audit) / MIT-0 (arc-agi-2-occam-baseline); FAIR EXP-001 is
the authors' own work. Built by the GrobeStreet research crew.

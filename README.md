# RCV-Bench — Research-Claim Verification Benchmark

**Can an agent tell whether a claimed research result is actually supported?** RCV-Bench scores an agent on verifying or refuting a claimed numeric result given the claim and its code: regenerate the number, catch a planted defect, probe a declared robustness condition, and surface calibrated uncertainty.

The benchmark is built around a simple distinction: **re-execution is not the same thing as verification.**

## v1 harness

`harness/run.py --command ...` creates a sanitized per-task workspace, withholds `GOLD/`, sends the task packet to an external process, validates the returned JSON verdict, records runtime/errors, and writes predictions consumable by the scorer. See [`harness/AGENT_PROTOCOL.md`](harness/AGENT_PROTOCOL.md).

Verdict classes:

`REPRODUCED` · `DEVIATION` · `FABRICATED` · `FRAGILE`

A verdict object includes the verdict, regenerated value when available, localized cause, confidence, escalation flag, and evidence.

## Corpus — 14 instances across 4 source repositories

Spread: REPRODUCED 5 · DEVIATION 4 · FRAGILE 3 · FABRICATED 2.

| source repo | instances | example |
|---|---:|---|
| de-stress-lab | 6 | 2.75σ time-variation falls to 1.81σ when LRG2 is removed → **FRAGILE** |
| arc-agi-2-occam-baseline | 3 | earlier optimistic prefix analysis is overturned by stricter same-holdout analysis → **DEVIATION** |
| FAIR Universe EXP-001 | 3 | externally-gated weak-lensing cases used to test deviation/fabrication logic |
| mmlu-robustness-audit | 2 | ~78% underlying-answer flip rate under cyclic option reorder → **FRAGILE** |

### FAIR evidence-state correction

The three FAIR tasks are **external-gated** because the full Phase-2 data and Codabench execution are not reproduced inside this benchmark workflow. Earlier wording called their numerical records “externally verified receipts.” That was too strong relative to the current canonical [`GrobeStreet/fair-universe-2026`](https://github.com/GrobeStreet/fair-universe-2026) repository, whose public submission registry does not yet contain a recorded project-specific Codabench score.

Until those receipts are anchored in the canonical FAIR repository, RCV-Bench treats the FAIR numerical arc as a **documented project record used for task logic, not independently verified benchmark gold**. The canonical FAIR repository is the authority for external-score status.

`build_tasks_reconciled.py` is the current authoritative task-tree build entry point. It runs the legacy deterministic generator and then enforces this corrected FAIR evidence state. CI verifies that its output exactly matches the committed task tree.

## Reference baselines

| system | verdict acc | macro-F1 | FRAGILE recall | FABRICATED recall |
|---|---:|---:|---:|---:|
| always-REPRODUCED | 5/14 (0.357) | 0.132 | 0/3 | 0/2 |
| naive-rerun | 9/14 (0.643) | 0.392 | 0/3 | 0/2 |
| perfect ceiling | 14/14 (1.000) | 1.000 | 3/3 | 2/2 |

The naive-rerun policy recomputes the headline but does not probe the declared perturbation or provenance failure mode. It therefore looks competent overall while missing every FRAGILE and FABRICATED task.

## First real-agent baseline

On 2026-08-26 the public GitHub Actions workflow ran a real autonomous local agent using **Ollama `qwen2.5-coder:1.5b`**, with no provider API and zero personal API spend. The run used a sanitized task workspace, withheld gold, blocked agent network access by policy, exposed only bounded local tools, and allowed at most 8 agent steps per task.

Result on all 14 tasks:

| metric | result |
|---|---:|
| verdict accuracy | **6/14 (0.429)** |
| macro-F1 | **0.339** |
| FRAGILE recall | **0/3** |
| FABRICATED recall | **1/2** |
| defect localization | **0/9** |
| Brier score | **0.266** |

This is **not a frontier-model claim**. It is the first end-to-end real-agent baseline demonstrating that tool use and autonomous execution do not by themselves produce robust claim-verification behavior. The run artifact and execution trace are preserved in GitHub Actions from workflow run `33020049937`.

## Run it

```bash
python3 build_tasks_reconciled.py
python3 baselines/always_reproduced.py
python3 baselines/naive_rerun.py
python3 scoring/score.py baselines/predictions_naive_rerun.json --name naive-rerun

python3 harness/run.py \
  --command "python3 /absolute/path/to/agent_adapter.py" \
  --out predictions_external.json \
  --trace trace.jsonl

python3 scoring/score.py predictions_external.json --name external-agent
```

A zero-API-cost reference workflow is also included under `.github/workflows/real-agent-baseline.yml`.

## Layout

```text
tasks/<id>/  claim.json · README.md · GOLD/gold.json
harness/     external-process runner, protocol, adapters, traces
baselines/   deterministic floor policies
scoring/     verdict/class metrics, localization, calibration
leaderboard/ public result presentation
```

## Provenance and limits

- Eleven tasks can be regenerated in the benchmark environment or through the included local reproduction path.
- The three FAIR tasks remain external-gated; their current numerical records must not be described as independently verified until the canonical FAIR repository anchors the relevant external receipts.
- Public gold exists for auditability, so publishable agent results require an execution boundary that prevents the agent from reading the benchmark checkout or public gold during the run.
- The first real-agent result above is a small open-weight baseline, not a general statement about frontier systems.

## Next decisive work

1. Run stronger real agents under the same declared isolation/tool/network budget.
2. Anchor or withdraw the FAIR external-score receipts in the canonical FAIR project.
3. Add held-out/private task packs so agents cannot exploit public gold.
4. Expand the corpus only after the evaluation boundary is stronger.

## License

Benchmark code: Apache-2.0. Task data and gold: CC BY 4.0. Source repositories retain their own licenses. Built by the GrobeStreet research crew.

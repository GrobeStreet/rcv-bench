# RCV-Bench — Research-Claim Verification Benchmark

**Can an agent tell whether a claimed research result is actually supported?** RCV-Bench evaluates a capability that ordinary reruns do not: given a claim and its code/evidence, can an agent regenerate the result, distinguish a real deviation from an execution problem, catch missing or fabricated support, probe a declared robustness condition, and express uncertainty without seeing the answer key?

The benchmark is built around a simple distinction: **re-execution is not the same thing as verification.**

**Dataset on Hugging Face:** [GrobeStreet/rcv-bench](https://huggingface.co/datasets/GrobeStreet/rcv-bench) — same corpus, card, and baselines (CC BY 4.0).

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
| task-type-shortcut | 8/14 (0.571) | 0.406 | **3/3** | 0/2 |
| README shortcut (probe, fixed) | 5/14 (0.357) | 0.132 | 0/3 | 0/2 |
| perfect ceiling | 14/14 (1.000) | 1.000 | 3/3 | 2/2 |

The naive-rerun policy recomputes the headline but does not probe the declared perturbation or provenance failure mode. It therefore looks competent overall while missing every FRAGILE and FABRICATED task.

### Fixed: the task README leaked gold (v1, found and closed 2026-11-26)

`harness/run.py::sanitized_task()` copies `tasks/<id>/README.md` into the directory the agent
reads, and in v1 that file was the **curator note**. Nine of the fourteen notes stated their own
gold verdict in prose ("Correct verdict: FRAGILE"), and several printed the gold regenerated
values the scorer compares against.

`baselines/readme_verdict_shortcut.py` measures it. The policy opens `README.md`, regexes out a
verdict-class token, returns it, and performs **no verification of any kind**:

| | verdict acc | macro-F1 | FRAGILE recall | FABRICATED recall |
|---|---:|---:|---:|---:|
| README shortcut, v1 tree | **1.000 (14/14)** | **1.000** | 3/3 | 2/2 |
| README shortcut, after fix | 0.357 (5/14) | 0.132 | 0/3 | 0/2 |

A perfect score with no work done. **Any RCV-Bench v1 number produced by an agent that read
`README.md` is uninterpretable**, which includes the external-agent protocol as documented, since
`AGENT_PROTOCOL.md` instructs agents to inspect files in the task directory. In practice the
published baselines are unaffected -- `always-REPRODUCED`, `naive-rerun` and `task-type-shortcut`
never open the README, and the `qwen2.5-coder:1.5b` run had access and did not exploit it -- but
the channel was open to any capable agent, so those scores were luck, not design.

The fix: curator prose moved to `GOLD/CURATOR_NOTES.md` (never copied), the agent-visible README
is generated from the claim packet by `harness/task_readme.py`, both task builders write through
that one function, and `tests/test_no_gold_leakage.py` fails CI if a verdict class appears in any
agent-visible file or if the shortcut ever beats the floor again. The probe baseline is kept as a
permanent regression check rather than deleted.

### Known leakage: FRAGILE recall is gameable in v1

In the v1 corpus `task_type == "ROBUST"`, the presence of a `perturbation` block, and
`gold == FRAGILE` are perfectly aligned (3/3), and the `ROBUST` verdict class is declared but
never used as gold. The `task-type-shortcut` baseline exploits exactly that: it reads only the
structural tell, performs no verification at all, and still takes **FRAGILE recall 3/3 (F1 1.00)** --
a metric on which every other baseline, including the real local agent, scores 0/3. Its verdict
accuracy (0.571) stays below naive-rerun (0.643). Its macro-F1 (0.406) is nominally above
naive-rerun's (0.392), but that 0.014 gap on 14 instances is inside noise and is not a ranking.

The finding rests on three instances, so the claim is deliberately narrow: the `ROBUST` class is
unpopulated in v1 and its task type is a one-to-one tell, which makes FRAGILE recall uninformative
on this corpus.

Withholding `task_type` would not close this, because the `perturbation` block carries the same
signal. Closing it properly requires v2 instances whose declared perturbation **holds** (gold
`ROBUST`), so the robustness task type stops being a one-to-one tell. Until then, FRAGILE recall
on v1 is uninformative unless an agent also beats this shortcut on macro-F1 and localization.

Found by an external interoperability test; see
[`harness/RESEARCHGYM_INTEROP.md`](harness/RESEARCHGYM_INTEROP.md).

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

## Evaluate your own agent

The v1 harness accepts any external process that reads one task JSON from stdin and emits one verdict JSON to stdout. External runs are welcome. For a result to be interpretable, record the model/agent version, tool policy, network policy, time/step budget, and isolation boundary. Public benchmark gold must not be visible to the agent during execution.

**Want to contribute a run?** Use [issue #3](https://github.com/GrobeStreet/rcv-bench/issues/3) as the public coordination thread.

## Run it

```bash
python3 build_tasks_reconciled.py
python3 baselines/always_reproduced.py
python3 baselines/naive_rerun.py
python3 baselines/task_type_shortcut.py
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
- Public task content can also create memorization/contamination risk for pretrained systems; held-out/private packs are a stronger future evaluation condition.
- The first real-agent result above is a small open-weight baseline, not a general statement about frontier systems.

## Next decisive work

1. Run stronger real agents under the same declared isolation/tool/network budget.
2. Anchor or withdraw the FAIR external-score receipts in the canonical FAIR project.
3. Add v2 instances whose declared perturbation holds (gold `ROBUST`), closing the task-type tell.
4. Add held-out/private task packs so agents cannot exploit public gold.
5. Expand the corpus only after the evaluation boundary is stronger.

## License

Benchmark code: Apache-2.0. Task data and gold: CC BY 4.0. Source repositories retain their own licenses. Built by the GrobeStreet research crew.

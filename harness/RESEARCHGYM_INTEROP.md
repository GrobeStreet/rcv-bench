# RCV-Bench × ResearchGym interoperability report

**Date:** 2026-11-26
**Scope:** can [ResearchGym](https://github.com/Anikethh/ResearchGym) agents be run against RCV-Bench tasks?
**Context:** the ResearchGym maintainer invited an external interoperability test in
[ResearchGym#4](https://github.com/Anikethh/ResearchGym/issues/4) ("Feel free to use or adapt
ResearchGym's agents for your benchmark… we'd be interested to hear how it goes, including any
failures or incompatibilities you find").

**Artifact:** [`harness/rcv_researchgym_adapter.py`](rcv_researchgym_adapter.py). Additive: it changes
nothing in RCV-Bench's existing code and nothing in ResearchGym, consuming a ResearchGym checkout via
`RESEARCHGYM_ROOT`.

---

## What was and was not established

**Established.** A translation layer between the two frameworks exists and holds at both ends:

| check | result |
|---|---|
| RCV-Bench harness accepts the adapter across the corpus | **14 / 14 tasks**, 0 schema violations |
| ResearchGym's own `run_agent.py` accepts a translated task and plans a run | **yes** — exit 0, `plan.json` written, RGAgent resolved |
| adapter overhead per task | ~0.03 s |

**Not established.** **No ResearchGym agent was ever executed. Zero model calls were made.** Whether an
RGAgent can actually verify a research claim is untested here, because execution costs real inference
money. Everything below concerns plumbing and contracts, not agent capability.

The bundled `mock` backend is a protocol-conformance harness. It scored 0.357 verdict accuracy, which
is *exactly* the always-REPRODUCED floor (5/14) by construction. **It is not a capability result and
must not be cited as one.**

---

## The core incompatibility: two different agent contracts

| | ResearchGym | RCV-Bench |
|---|---|---|
| input | task **directory** (`task_description.md`, `grading/grade.sh`, baselines) | **claim packet** JSON on stdin |
| agent goal | **maximise a numeric score** over 12–24 h | **return a bounded structured verdict** |
| output | a workspace, graded by `grade.sh` → a number | one JSON object: verdict + confidence + localisation + evidence |
| scoring | improvement over a baseline score | accuracy, macro-F1, per-class recall, localisation, Brier |

These do not compose. Two translations are required:

1. **`build_rg_task()`** — renders a claim packet as a ResearchGym-shaped task directory.
2. **`extract_verdict()`** — reduces a free-form agent run back to a verdict. **This is the half
   ResearchGym cannot do natively.** Its agents have an `end_task()` control tool but no structured
   output contract, so the task description imposes a terminal block:

   ```
   <RCV_VERDICT>{"verdict": "...", "confidence": 0.0-1.0, "localized_cause": "...", ...}</RCV_VERDICT>
   ```

   A run that does not emit it is unscoreable.

---

## Incompatibilities and operational gotchas

1. **No structured-output contract.** The blocking one, handled by the imposed verdict block.
2. **`grade.sh` has no equivalent.** RCV-Bench scores a classification, so ResearchGym's grading path
   is bypassed entirely and the stub returns `{"score": null}`.
3. **Agent output is not on the CLI's stdout.** `run_agent.py` prints only orchestration messages;
   the agent transcript is persisted in the run directory. The adapter reads the paths out of
   ResearchGym's own `plan.json` (`RG_TRANSCRIPT_PATH`, `RG_LOG_DIR`) rather than guessing. An
   integration that parses `proc.stdout` will record every successful run as an error.
4. **The checkout must be importable as the package `ResearchGym`.** `run_agent.py` does
   `from ResearchGym.environment import AgenticEnv`, so a clone in a differently-named directory fails
   at import. Either `uv sync` it or put the parent directory on `PYTHONPATH` with the checkout named
   `ResearchGym`.
5. **Harness timeout must exceed the agent budget.** `harness/run.py` defaults to a 900 s per-task
   timeout while ResearchGym derives its limit from `--basic_hours`; a 0.5 h agent run needs an
   explicit `--timeout` above 1860 s or it is killed mid-run and recorded as `agent-error`.
6. **Budget asymmetry.** `plan.json` confirms `RG_BUDGET_LIMIT=10.0` per task. Across 14 tasks that is
   roughly **$140** at defaults, against RCV-Bench's existing real-agent baseline at ≤8 steps and $0.
   Cross-framework numbers need both budgets declared.
7. **Isolation.** The `uv` runtime executes locally with `bash()`/`python()`, so it can reach the
   parent checkout and read `GOLD/`. Publishable runs need ResearchGym's **Docker** runtime with only
   the sanitized directory mounted; the adapter exposes `--runtime docker --image ...` for this.
8. **Network exposure is conditional, not default.** RGAgent ships `web_search()`/`web_browser()`, and
   because RCV-Bench gold is public a web-enabled agent could look up the answer. However the planned
   configuration observed here sets `DISABLE_BROWSER=true`, `USE_EXA_SEARCH=false` and
   `USE_GOOGLE_WEB_SEARCH=false`, so the default posture is safe. The risk applies only if those are
   enabled, and the network policy must be declared either way.

---

## Two leakage issues this test surfaced in RCV-Bench itself

### 1. The agent-visible README carried the gold verdict

Building the sanitized workspace for this test meant reading
`harness/run.py::sanitized_task()` closely, which copies `tasks/<id>/README.md` into the directory
the agent reads. In v1 that file was the curator note: 9 of 14 stated the gold verdict in prose and
several printed the gold regenerated values. `baselines/readme_verdict_shortcut.py` greps it,
performs no verification, and scored **14/14 verdict accuracy, macro-F1 1.000** on the v1 tree.

Fixed the same day: curator prose moved to `GOLD/CURATOR_NOTES.md`, the agent-visible README is
generated from the claim packet, and `tests/test_no_gold_leakage.py` fails CI if a verdict class
reappears in any agent-visible file. The probe now scores 0.357, the always-REPRODUCED floor.

This matters for any cross-framework comparison: an RCV-Bench score from an agent that read
`README.md` on the v1 tree is uninterpretable. The numbers in this report are unaffected -- the
mock backend never opens it -- but a live RGAgent run would have had the answer in its workspace.

### 2. `task_type` is a one-to-one tell for FRAGILE

- The sanitized packet exposes `task_type`.
- **All three `ROBUST`-type tasks have gold `FRAGILE`** (`ds-fragile-01`, `arc-leaderboard-01`,
  `mmlu-flip-01`), and the `ROBUST` verdict class is **declared but never used** as gold in v1.
- The tell is **redundant**: `task_type == "ROBUST"` and the presence of a `perturbation` block are
  co-extensive, so suppressing one field does not close the channel.

`baselines/task_type_shortcut.py` quantifies it. The policy reads only the structural tell and
performs no verification:

| system | verdict acc | macro-F1 | FRAGILE recall |
|---|---:|---:|---:|
| always-REPRODUCED | 0.357 | 0.132 | 0/3 |
| naive-rerun | 0.643 | 0.392 | 0/3 |
| real agent (qwen2.5-coder:1.5b) | 0.429 | 0.339 | 0/3 |
| task-type-shortcut | 0.571 | 0.406 | **3/3 (F1 1.00)** |

**The load-bearing result is FRAGILE recall: 3/3 without any verification**, on a metric where every
other baseline scores 0/3. Read the macro-F1 column with care — 0.406 against naive-rerun's 0.392 is a
0.014 difference on 14 instances, which is well inside noise and is **not** a ranking. Verdict accuracy
remains below naive-rerun.

The finding also rests on **three instances**, so the accurate statement is narrow: *the `ROBUST` class
is unpopulated in v1 and its task type is a one-to-one tell, which makes FRAGILE recall uninformative
on this corpus.*

**Done now:** the shortcut is published as a floor baseline and documented, so the number is on the
record rather than waiting to be discovered. **Still required (v2):** instances whose declared
perturbation *holds*, giving `ROBUST` real gold support. No gold was fabricated for this report.

---

## Reproducing

```bash
# offline, zero cost
python3 harness/run.py \
  --command "python3 $PWD/harness/rcv_researchgym_adapter.py --backend mock --work-root /tmp/rcv-rg-work" \
  --out predictions_researchgym_mock.json --trace trace_researchgym_mock.jsonl
python3 scoring/score.py predictions_researchgym_mock.json --name rg-mock-interop

# plan a real run without spending anything (needs no API key)
export RESEARCHGYM_ROOT=/path/to/ResearchGym      # directory must be named ResearchGym
export PYTHONPATH=$(dirname "$RESEARCHGYM_ROOT")
echo "$TASK_PACKET" | python3 harness/rcv_researchgym_adapter.py --backend rgagent --dry-run
```

A live run additionally needs a provider key and a timeout above the agent budget:

```bash
python3 harness/run.py --timeout 2400 \
  --command "python3 $PWD/harness/rcv_researchgym_adapter.py --backend rgagent \
             --runtime docker --image researchgym-rg-agent:latest --model openai/gpt-5 --hours 0.5" \
  --out predictions_rgagent.json --trace trace_rgagent.jsonl
```

Per [`AGENT_PROTOCOL.md`](AGENT_PROTOCOL.md), a publishable score must declare model version,
container digest, network policy, time/step budget and tool permissions.

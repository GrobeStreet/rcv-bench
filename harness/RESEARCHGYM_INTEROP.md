# RCV-Bench × ResearchGym interoperability report

**Date:** 2026-11-26
**Scope:** can [ResearchGym](https://github.com/Anikethh/ResearchGym) agents be run against RCV-Bench tasks?
**Context:** ResearchGym maintainer invited an external interoperability test in
[ResearchGym issue #4](https://github.com/Anikethh/ResearchGym/issues/4) ("Feel free to use or adapt
ResearchGym's agents for your benchmark… we'd be interested to hear how it goes, including any
failures or incompatibilities you find").

**Artifact:** [`harness/rcv_researchgym_adapter.py`](rcv_researchgym_adapter.py) — additive. It changes
nothing in RCV-Bench's existing code and nothing in ResearchGym; it consumes a ResearchGym checkout
via `RESEARCHGYM_ROOT`.

---

## Headline result

**The two frameworks do interoperate, but not directly — a two-way translation layer is required,
and one of the two directions has no native support on the ResearchGym side.**

The adapter was run through RCV-Bench's own `harness/run.py` across all 14 tasks, offline, at zero
API cost. All 14 round-tripped cleanly:

`RCV claim packet → ResearchGym task directory → agent transcript → verdict block → validated RCV verdict → scorer`

| check | result |
|---|---|
| tasks completed through the process contract | **14 / 14** |
| malformed stdout / schema violations / harness errors | **0** |
| mean per-task adapter overhead | ~0.03 s |
| live-agent path (`--backend rgagent`) | reaches the paid-inference boundary and stops |

**The offline score is not a capability result.** The `mock` backend is a deliberately
non-inferential protocol-conformance harness. It scored 0.357 verdict accuracy — *exactly* the
always-REPRODUCED floor (5/14), by construction. It must never be cited as agent performance.

One incidental calibration note: the mock's Brier score (0.233) is better than the naive-rerun
baseline's (0.266) purely because it states an honest low confidence (0.30) while being wrong.
That is a property of calibration, not of competence, and it illustrates why RCV-Bench scores
confidence separately from accuracy.

---

## The core incompatibility: two different agent contracts

| | ResearchGym | RCV-Bench |
|---|---|---|
| input | task **directory** (`task_description.md`, `grading/grade.sh`, baselines) | **claim packet** JSON on stdin |
| agent goal | **maximise a numeric score** over 12–24 h | **return a bounded structured verdict** |
| output | a workspace, graded by `grade.sh` → a number | one JSON object: verdict + confidence + localisation + evidence |
| scoring | improvement over a baseline score | accuracy, macro-F1, per-class recall, localisation, Brier |

These do not compose. Bridging needs two translations, both implemented in the adapter:

1. **`build_rg_task()`** — renders a claim packet as a ResearchGym-shaped task directory: a
   `task_description.md` that frames verification as the research goal (claim, metric, tolerance,
   declared perturbation, verdict definitions), a `grading/grade.sh` stub, and the sanitized
   materials under `input/`.
2. **`extract_verdict()`** — reduces a free-form agent run back to a verdict. **This is the half
   ResearchGym cannot do natively.** Its agents have an `end_task()` control tool but no structured
   output contract, so the task description imposes a terminal machine-readable block:

   ```
   <RCV_VERDICT>{"verdict": "...", "confidence": 0.0-1.0, "localized_cause": "...", ...}</RCV_VERDICT>
   ```

   A run that does not emit this block is unscoreable and counts as an error.

---

## Incompatibilities found

1. **No structured-output contract (blocking without the adapter).** As above: imposed via a
   terminal verdict block. Any benchmark needing typed output from a ResearchGym agent will hit this.
2. **`grade.sh` has no meaningful equivalent.** RCV-Bench scores a classification, not a submission
   artifact. The stub returns `{"score": null}` and the authoritative path stays `scoring/score.py`.
   ResearchGym's grading pipeline is bypassed entirely.
3. **Budget and runtime mismatch.** ResearchGym assumes 12–24 h and a **$10 API budget per task**.
   Across RCV-Bench's 14 tasks that is roughly **$140 and several days** at defaults. RCV-Bench's own
   first real-agent baseline ran at **≤8 steps per task and $0**. The two budget regimes are not
   comparable, so a cross-framework score needs the budget declared on both axes.
4. **Network access breaks the evaluation boundary.** RGAgent ships `web_search()` and
   `web_browser()`. RCV-Bench gold is **public** (this repo and the Hugging Face dataset), so a
   web-enabled agent can simply look up the answer. **Any publishable cross-framework score must
   disable network access and declare it.** This is the most serious integrity issue found.
5. **Filesystem isolation.** RCV-Bench already warns that the sanitized directory is not a hard
   boundary. ResearchGym's `uv` runtime executes locally with `bash()`/`python()`, so the agent can
   reach the parent checkout and read `GOLD/`. Publishable runs need ResearchGym's **Docker** runtime
   (or a VM) with only the sanitized directory mounted.
6. **Dependency floor.** ResearchGym needs Python ≥ 3.12 and `uv`; some tasks additionally need
   Docker and GPUs. RCV-Bench needs only Python 3 + numpy/scipy/pandas/scikit-learn. Verified working
   here on Python 3.13 with `uv` present — the dependency gap is real but not an obstacle.

---

## A defect this test surfaced in RCV-Bench itself

Running an external framework against the corpus exposed a **label-leakage channel in RCV-Bench v1**:

- The sanitized packet exposes `task_type`.
- **All three `ROBUST`-type tasks have gold `FRAGILE`** (`ds-fragile-01`, `arc-leaderboard-01`,
  `mmlu-flip-01`).
- The `ROBUST` verdict class is **declared but never used** by any v1 instance.

So an agent can score **3/3 FRAGILE recall** — a headline metric on which the naive-rerun baseline
scores 0/3 — by mapping `task_type == ROBUST → FRAGILE`, with no verification capability whatsoever.
`REPRO` is less degenerate but still narrows the space to three classes.

**Recommended fix:** add instances whose declared perturbation *holds*, so `ROBUST` is a real gold
label and the `ROBUST` task type stops being a one-to-one tell. Optionally withhold `task_type` from
the sanitized packet, or report FRAGILE recall alongside a task-type-blind control.

This matters beyond this experiment: it means the current FRAGILE-recall figures distinguish agents
only because none of them have exploited the shortcut yet.

---

## Reproducing

```bash
# offline, zero cost — proves the full contract
python3 harness/run.py \
  --command "python3 $PWD/harness/rcv_researchgym_adapter.py --backend mock --work-root /tmp/rcv-rg-work" \
  --out predictions_researchgym_mock.json \
  --trace trace_researchgym_mock.jsonl

python3 scoring/score.py predictions_researchgym_mock.json --name rg-mock-interop
```

A live ResearchGym run (**bills real money**) additionally needs a ResearchGym checkout, `uv`, and a
provider key. The adapter checks each prerequisite and raises explicitly rather than degrading:

```bash
export RESEARCHGYM_ROOT=/path/to/ResearchGym
export OPENAI_API_KEY=...          # or ANTHROPIC_API_KEY / GEMINI_API_KEY
python3 harness/run.py \
  --command "python3 $PWD/harness/rcv_researchgym_adapter.py --backend rgagent --model openai/gpt-5 --hours 0.5" \
  --out predictions_rgagent.json --trace trace_rgagent.jsonl
```

For a publishable number that run must be executed under ResearchGym's Docker runtime with network
disabled and only the sanitized task directory mounted, and must declare model version, container
digest, network policy, time/step budget, and tool permissions, per
[`AGENT_PROTOCOL.md`](AGENT_PROTOCOL.md).

---

## Status

- Interoperability: **demonstrated**, offline, 14/14, zero cost.
- Live agent run: **not performed** — blocked only by paid inference, not by any technical gap.
- Capability comparison between ResearchGym agents and existing RCV-Bench baselines: **not yet
  established**, and nothing here should be read as one.

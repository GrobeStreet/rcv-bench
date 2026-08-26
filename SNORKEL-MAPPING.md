# RCV-Bench → Snorkel Open Benchmarks axes

Snorkel's [RFP](https://benchmarks.snorkel.ai/closing-the-evaluation-gap-in-agentic-ai/) frames
agentic evaluation on three axes. RCV-Bench is built primarily on **output complexity**, with
real load on **environment complexity**, and a defined path to **autonomy horizon** in v1.

## 1. Output complexity — the core fit
Snorkel wants *"nuanced, multi-factor rubrics and reward signals beyond pass/fail"* and
*"trustworthy outputs that surface uncertainty and recognize escalation needs."* That is
exactly the RCV-Bench verdict object and scorer.

| Snorkel ask | RCV-Bench mechanism |
|---|---|
| beyond pass/fail | 5-way verdict (REPRODUCED/DEVIATION/FABRICATED/ROBUST→FRAGILE), not binary |
| multi-factor rubric | scorer = macro-F1 + per-class P/R/F1 + FRAGILE & FABRICATED recall + localization + Brier |
| surface uncertainty | every verdict carries a calibrated `confidence`; scored by Brier |
| recognize escalation | `escalate` flag graded when a claim is genuinely unreproducible |
| localize, don't just judge | `localized_cause` graded on defect cases (sign-inversion, hash-mismatch, pin-drift, selection-bias) |

Evidence it bites: the `naive-rerun` baseline scores 0/2 on FABRICATED because it can't
distinguish "wrong number" from "invented result" — a distinction only a multi-factor rubric captures.

## 2. Environment complexity — real, not synthetic
Snorkel wants *domain nuance, realistic tool complexity, ambiguous documentation.* RCV-Bench
instances are **real public research repos**, not toy tasks: DESI DR2 cosmology likelihoods,
ARC-AGI-2 program synthesis, weak-lensing OoD detection, MMLU option-order robustness. The
agent must check out a pinned commit, build the environment, and run the actual code —
including repos whose own READMEs disagree with their manifests, and frozen-vs-regenerated
records that must be read correctly.

| Snorkel ask | RCV-Bench mechanism |
|---|---|
| domain-specific nuance | 4 distinct scientific/ML domains, each with its own metric and failure mode |
| realistic tool complexity | real pinned repos, real install/run, real deterministic-seed requirements |
| noisy / ambiguous context | source READMEs that mis-summarize their own results; agent must trust regeneration over prose |

## 3. Autonomy horizon — v1 path
Snorkel wants *long-trajectory reliability* and *adaptation to non-stationary goals.* v0 tasks
are single-claim (short horizon). The **ROBUST** tasks already require a two-phase trajectory
(reproduce → perturb → re-decide), and v1 extends to multi-claim papers (verify a full results
table, propagate a caught defect across dependent claims) — a genuine long-horizon agentic task.

## Why this lane is open
The funded first cohort covers coding/SWE, terminal, computer-use, continual-learning, and
code-quality agents. **None evaluate whether an agent can verify a research claim** — regenerate
it, catch a planted or real defect, and judge robustness. RCV-Bench is that missing axis, built
from a crew that already ships reproducibility audits (github.com/grobestreet) and holds an
externally-graded receipt (FAIR EXP-001, Codabench #10902).

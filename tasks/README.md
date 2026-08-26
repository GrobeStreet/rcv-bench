# RCV-Bench v0 — task packets (real gold, ready to scaffold against)

**Fourteen** seed instances across four repos for the Research-Claim-Verification
benchmark. Eleven are **regenerated in-sandbox** (incl. MMLU via `harness/mmlu_live.py`);
three (`fair-*`) are **external-gated** on the 8.7 GB FAIR dataset — gold from the
externally-graded Codabench receipt; live re-run is v1. Spread: REPRODUCED 5 · DEVIATION 4 · FRAGILE 3 · FABRICATED 2.
`INDEX.json` lists them all. Pins: de-stress-lab `7290d788…`, arc-agi-2-occam `ef7fb14a…`,
mmlu-robustness-audit `25bf51f5…`, FAIR EXP-001 `f5def09c`.

## Layout (per instance)
```
tasks/<id>/
  claim.json      # EXACTLY what the agent-under-test sees (no gold fields)
  README.md       # one-line human description
  GOLD/gold.json  # public v0 scoring ground truth; evaluator withholds it from agent input:
                  #   confidence, escalate, evidence, regeneration_status
  env/            # (only ds-integrity-02) staged tampered artifact + original sidecar
```

## The fourteen instances
| id | type | gold verdict | execution | what it tests |
|----|------|--------------|-----------|---------------|
| ds-repro-01 | REPRO | REPRODUCED | in-sandbox | exact number match (`destress demo` bao_chi2=10.5547) |
| ds-integrity-01 | REPRO | REPRODUCED | in-sandbox | frozen-ledger hash verifies |
| ds-integrity-02 | REPRO | DEVIATION | in-sandbox | catch a tampered ledger (hash-mismatch) — **planted** |
| ds-audit-01 | REPRO | REPRODUCED | in-sandbox | reproducibility-readiness audit = 100/100 |
| ds-fragile-01 | ROBUST | FRAGILE | in-sandbox | **marquee**: headline survives full data, collapses when LRG2 deleted (2.75σ→1.81σ) |
| ds-fabricate-01 | REPRO | FABRICATED | in-sandbox | claim the code never produces — **planted** |
| arc-repro-01 | REPRO | REPRODUCED | in-sandbox | seeded bootstrap reproduces candidate-reliability 32.8/50.8/63.4 |
| arc-selfcorrect-01 | REPRO | DEVIATION | in-sandbox | old prefix claim (50/87/95, +24pt) overturned by same-holdout (32.8/50.8/63.4, +11.1) |
| arc-leaderboard-01 | ROBUST | FRAGILE | in-sandbox | N=120 'SOTA gap' fails power check (p=0.16; needs 1,566 tasks) |
| fair-repro-01 | REPRO | REPRODUCED | external | PS baseline 0.2092 (~17x chance) |
| fair-deviation-01 | REPRO | DEVIATION | external | **real bug**: OoD sign inversion → 0.00457 below chance — **planted** |
| fair-fabricate-01 | REPRO | FABRICATED | external | prize-looking 0.28 with no artifact — **planted** |
| mmlu-flip-01 | ROBUST | FRAGILE | in-sandbox | MMLU accuracy fragile to option reorder (78.33% answer flips) |
| mmlu-calib-deviation-01 | REPRO | DEVIATION | in-sandbox | frozen calibration metrics don't reproduce (ECE 0.28→0.137) |

Verdict classes: REPRODUCED · DEVIATION · FABRICATED · ROBUST · FRAGILE.

## How to regenerate the gold (independence check — the whole point)
```bash
git clone https://github.com/grobestreet/de-stress-lab && cd de-stress-lab
git checkout 7290d788af7f537643a6d85eb378380f019d5deb
pip install -e .
destress demo                                   # -> bao_chi2 = 10.554718768447175   (ds-repro-01)
destress verify-ledger predictions/2027-ledger.json   # -> sha256:84caead1...        (ds-integrity-01)
destress audit-repo .                            # -> 100/100 Grade A                 (ds-audit-01)
python3 scripts/time_variation_mocks.py --mocks 20 --fresh --output /tmp/f.json          # observed T=7.8506
python3 scripts/time_variation_mocks.py --mocks 20 --fresh --drop-index 2 --output /tmp/d.json  # observed T=3.4263
# full calibrated sigma (2.7478 full / 1.8132 no-LRG2): same command with --mocks 5000 --workers 8
```
Every `ds-*` gold value above is reproducible from these commands. `../build_tasks.py`
regenerates the whole tree deterministically.

ARC (`arc-*`, in-sandbox):
```bash
git clone https://github.com/grobestreet/arc-agi-2-occam-baseline && cd arc-agi-2-occam-baseline
git checkout ef7fb14abe0ea28ce39b952161c2e605de52f02e && pip install -r requirements.txt
python3 crossfold_analysis.py --input results/crossfold/crossfold_training.parquet \
  --results-dir out --bootstrap 20000 --seed 20260727   # candidate reliability 32.8/50.8/63.4 (arc-repro-01, arc-selfcorrect-01)
python3 leaderboard_stats.py                              # SOTA gap p=0.16; 5-pt gap needs n=1,566 (arc-leaderboard-01)
```
MMLU (`mmlu-*`, in-sandbox):
```bash
git clone https://github.com/grobestreet/mmlu-robustness-audit && cd mmlu-robustness-audit
git checkout 25bf51f555d388c5ddb823c0c513670b9fe45332 && pip install datasets transformers torch pandas pyarrow
PYTHONPATH=. python3 ../harness/mmlu_live.py --n 300 --dtype float32 --batch-size 16 --out /tmp/mmlu.parquet
# -> flip rate 78.33%, headline acc 44.00%, ECE 0.1367 (exact match to the repo's fp32 record)
```
`mmlu_live.py` is a batched reproduction of the repo's `audit_full.py` (same pins/prompt/scoring); ~15 min on 2 CPUs.

## For the harness
- `harness/run.py` feeds `claim.json` to an agent-under-test, enforces the §2 protocol
  from the spec, and collects the verdict object; **never expose `GOLD/`** to the agent.
- `scoring/score.py` compares the agent verdict to `GOLD/gold.json`: macro-F1 over the 5
  verdict classes, localization match, Brier/ECE on `confidence`, escalation P/R.
- Split by `execution`: `in_sandbox_regenerated` instances run end-to-end today;
  `external_gated` (FAIR) instances score the verdict logic now, live re-run in v1.
- Ship two baselines (`always-REPRODUCED`, `naive-rerun-no-perturbation`) to show headroom —
  the naive baseline should fail `ds-fragile-01` and every planted case, which is the point.

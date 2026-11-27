# arc-repro-01

Verification task. The claim under test is `claim.json` in this directory;
it is also delivered to the agent on stdin (see `harness/AGENT_PROTOCOL.md`).

- **Source repository:** https://github.com/grobestreet/arc-agi-2-occam-baseline
- **Pinned commit:** ef7fb14abe0ea28ce39b952161c2e605de52f02e
- **Metric:** same-holdout cross-fold candidate reliability by k (20000-bootstrap, task-clustered)
- **Reproduction entrypoint:** pip install -r requirements.txt && python3 crossfold_analysis.py --input results/crossfold/crossfold_training.parquet --results-dir out --bootstrap 20000 --seed 20260727
- **Network policy:** none

Read `claim.json` in full before deciding; it carries every field that defines
the task, including any declared perturbation. Emit exactly one verdict JSON
object on stdout.

Curator commentary and gold values are held in `GOLD/`, which is withheld from
the agent-visible directory.

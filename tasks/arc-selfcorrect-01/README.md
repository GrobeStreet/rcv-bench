# arc-selfcorrect-01

Verification task. The claim under test is `claim.json` in this directory;
it is also delivered to the agent on stdin (see `harness/AGENT_PROTOCOL.md`).

- **Source repository:** https://github.com/grobestreet/arc-agi-2-occam-baseline
- **Pinned commit:** ef7fb14abe0ea28ce39b952161c2e605de52f02e
- **Metric:** ARC demonstration-consistent -> held-out reliability calibration + selection lever
- **Reproduction entrypoint:** python3 crossfold_analysis.py ... (same-holdout) vs the earlier prefix analysis
- **Network policy:** none

Read `claim.json` in full before deciding; it carries every field that defines
the task, including any declared perturbation. Emit exactly one verdict JSON
object on stdout.

Curator commentary and gold values are held in `GOLD/`, which is withheld from
the agent-visible directory.

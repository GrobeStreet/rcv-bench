# arc-leaderboard-01

Verification task. The claim under test is `claim.json` in this directory;
it is also delivered to the agent on stdin (see `harness/AGENT_PROTOCOL.md`).

- **Source repository:** https://github.com/grobestreet/arc-agi-2-occam-baseline
- **Pinned commit:** ef7fb14abe0ea28ce39b952161c2e605de52f02e
- **Metric:** pairwise Wilson/permutation significance of adjacent leaderboard gaps + power analysis
- **Reproduction entrypoint:** python3 leaderboard_stats.py
- **Network policy:** none

Read `claim.json` in full before deciding; it carries every field that defines
the task, including any declared perturbation. Emit exactly one verdict JSON
object on stdout.

Curator commentary and gold values are held in `GOLD/`, which is withheld from
the agent-visible directory.

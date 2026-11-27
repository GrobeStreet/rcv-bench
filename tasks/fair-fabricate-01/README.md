# fair-fabricate-01

Verification task. The claim under test is `claim.json` in this directory;
it is also delivered to the agent on stdin (see `harness/AGENT_PROTOCOL.md`).

- **Source repository:** https://github.com/grobestreet/robert-morong-research (FAIR EXP-001; Codabench #10902 'FAIR Universe Weak Lensing Phase-2')
- **Pinned commit:** f5def09c
- **Metric:** mean TPR over 100 log-FPR points in [0.001, 0.05]
- **Reproduction entrypoint:** python ps_baseline.py --public

Read `claim.json` in full before deciding; it carries every field that defines
the task, including any declared perturbation. Emit exactly one verdict JSON
object on stdout.

Curator commentary and gold values are held in `GOLD/`, which is withheld from
the agent-visible directory.

# ds-integrity-02

Verification task. The claim under test is `claim.json` in this directory;
it is also delivered to the agent on stdin (see `harness/AGENT_PROTOCOL.md`).

- **Source repository:** https://github.com/grobestreet/de-stress-lab
- **Pinned commit:** 7290d788af7f537643a6d85eb378380f019d5deb
- **Metric:** frozen prediction-ledger SHA256
- **Reproduction entrypoint:** destress verify-ledger env/2027-ledger.json
- **Network policy:** none

Read `claim.json` in full before deciding; it carries every field that defines
the task, including any declared perturbation. Emit exactly one verdict JSON
object on stdout.

Curator commentary and gold values are held in `GOLD/`, which is withheld from
the agent-visible directory.

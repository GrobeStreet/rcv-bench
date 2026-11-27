# mmlu-calib-deviation-01

Verification task. The claim under test is `claim.json` in this directory;
it is also delivered to the agent on stdin (see `harness/AGENT_PROTOCOL.md`).

- **Source repository:** https://github.com/grobestreet/mmlu-robustness-audit
- **Pinned commit:** 25bf51f555d388c5ddb823c0c513670b9fe45332
- **Metric:** calibration/stability metrics (frozen historical reported values)
- **Reproduction entrypoint:** PYTHONPATH=<mmlu-repo> python3 harness/mmlu_live.py --n 300 --dtype float32 --batch-size 16  (batched reproduction of audit_full.py; Qwen2.5-0.5B-Instruct rev 7ae5576, cais/mmlu rev c30699e, seed 0). Regenerated in-sandbox 2026-08-26; metrics match the repo's fp32 column exactly.
- **Network policy:** hf-download

Read `claim.json` in full before deciding; it carries every field that defines
the task, including any declared perturbation. Emit exactly one verdict JSON
object on stdout.

Curator commentary and gold values are held in `GOLD/`, which is withheld from
the agent-visible directory.

#!/usr/bin/env python3
"""Build the RCV task tree, then enforce the current canonical FAIR evidence state.

The legacy task generator contains historical FAIR prose that called the external-gated
numerical records externally verified. The canonical fair-universe-2026 repository does not
yet publicly anchor those Codabench receipts, so this wrapper deliberately downgrades those
three task packets after deterministic generation.

Use this entry point for repository CI until the underlying generator is refactored.
"""
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
subprocess.run([sys.executable, str(ROOT / "build_tasks.py")], check=True)

packets = {
    "fair-deviation-01": {
        "readme": """Reproduction requires the 8.7 GB FAIR Universe Phase-2 dataset plus Codabench, so this task is `external_gated` and is not rerun inside RCV-Bench.

The task uses a documented project record in which a score-sign inversion produces a below-chance result and the expected verdict is `DEVIATION` with cause `score-sign-inversion`.

Important evidence-state limit: the current canonical `GrobeStreet/fair-universe-2026` public submission registry does not yet anchor the corresponding Codabench receipt. Therefore RCV-Bench must not describe this numerical record as independently verified external gold until that canonical project record is reconciled.
""",
        "gold": {
            "verdict": "DEVIATION",
            "regenerated_value": 0.00457,
            "localized_cause": "score-sign-inversion",
            "confidence": 0.95,
            "escalate": False,
            "regeneration_status": "documented_project_record; external_gated; Codabench receipt not yet anchored in canonical fair-universe-2026 public registry",
            "evidence": [
                "project record: inverted OoD score orientation produces 0.00457 below chance",
                "project record: corrected orientation is recorded as approximately 0.2092",
                "external receipt remains unverified by the canonical public FAIR submission registry",
            ],
            "planted_defect": True,
        },
    },
    "fair-fabricate-01": {
        "readme": """Reproduction requires the 8.7 GB FAIR Universe Phase-2 dataset plus Codabench, so this task is `external_gated` and is not rerun inside RCV-Bench.

The planted claim asserts a prize-looking `0.28` without a supporting submission artifact; the task is designed to test whether an agent treats an unsupported numerical claim as `FABRICATED` rather than rubber-stamping it.

Important evidence-state limit: earlier task prose treated the comparison value as an externally verified Codabench receipt. The current canonical `GrobeStreet/fair-universe-2026` public submission registry does not yet anchor that receipt, so RCV-Bench treats the FAIR numerical arc as a documented project record until the canonical project is reconciled.
""",
        "gold": {
            "verdict": "FABRICATED",
            "regenerated_value": 0.2092050284,
            "localized_cause": "doctored-value",
            "confidence": 0.9,
            "escalate": False,
            "regeneration_status": "documented_project_record; external_gated; comparison value not yet anchored as an external receipt in canonical fair-universe-2026 public registry",
            "evidence": [
                "the planted 0.28 claim has no supporting submission artifact",
                "the comparison value approximately 0.2092 is retained as a documented project record pending canonical receipt reconciliation",
            ],
            "planted_defect": True,
        },
    },
    "fair-repro-01": {
        "readme": """Reproduction requires the 8.7 GB FAIR Universe Phase-2 dataset plus Codabench, so this task is `external_gated` and is not rerun inside RCV-Bench.

The task represents the corrected FAIR power-spectrum baseline as the `REPRODUCED` case in the three-task FAIR bundle.

Important evidence-state limit: earlier prose described the numerical result as a live externally graded receipt. The current canonical `GrobeStreet/fair-universe-2026` public submission registry does not yet contain a project-specific Codabench score. Until that repository anchors the relevant receipt, RCV-Bench treats this as a documented project record used for task logic, not independently verified external gold.
""",
        "gold": {
            "verdict": "REPRODUCED",
            "regenerated_value": 0.2092050284,
            "delta_vs_claim": 0.0,
            "localized_cause": "none",
            "confidence": 0.95,
            "escalate": False,
            "regeneration_status": "documented_project_record; external_gated; external receipt not yet anchored in canonical fair-universe-2026 public registry",
            "evidence": [
                "published historical power-spectrum baseline reference is approximately 0.2143 on the pre-swap test set",
                "the approximately 0.2092 current-set value is retained as a documented project record pending canonical external-receipt reconciliation",
            ],
            "planted_defect": False,
        },
    },
}

for task_id, packet in packets.items():
    task_dir = ROOT / "tasks" / task_id
    (task_dir / "README.md").write_text(packet["readme"], encoding="utf-8")
    (task_dir / "GOLD" / "gold.json").write_text(
        json.dumps(packet["gold"], indent=2) + "\n", encoding="utf-8"
    )

print("reconciled FAIR external-gated evidence state against canonical public registry status")

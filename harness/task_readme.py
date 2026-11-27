"""Agent-facing task README generation.

Single source of truth, shared by both task builders.

Curator prose must never reach the agent-visible directory: several v1 notes
stated the gold verdict and the gold regenerated values outright, and
`harness/run.py::sanitized_task()` copies `README.md` into the directory the
agent reads. Curator commentary belongs in `GOLD/CURATOR_NOTES.md`.

See `baselines/readme_verdict_shortcut.py` for the probe that measures this, and
`tests/test_no_gold_leakage.py` for the guard that keeps it closed.
"""

VERDICT_CLASSES = ("REPRODUCED", "DEVIATION", "FABRICATED", "ROBUST", "FRAGILE")

_FIELDS = (
    ("Source repository", "source"),
    ("Pinned commit", "pin"),
    ("Metric", "metric"),
    ("Reproduction entrypoint", "entrypoint"),
)


def agent_readme(claim: dict) -> str:
    """Render the agent-visible README for a claim packet. Carries no gold."""
    lines = [
        f"# {claim['claim_id']}",
        "",
        "Verification task. The claim under test is `claim.json` in this directory;",
        "it is also delivered to the agent on stdin (see `harness/AGENT_PROTOCOL.md`).",
        "",
    ]
    for label, key in _FIELDS:
        if claim.get(key):
            lines.append(f"- **{label}:** {claim[key]}")
    network = (claim.get("env") or {}).get("network")
    if network:
        lines.append(f"- **Network policy:** {network}")
    lines += [
        "",
        "Read `claim.json` in full before deciding; it carries every field that defines",
        "the task, including any declared perturbation. Emit exactly one verdict JSON",
        "object on stdout.",
        "",
        "Curator commentary and gold values are held in `GOLD/`, which is withheld from",
        "the agent-visible directory.",
    ]
    return "\n".join(lines) + "\n"

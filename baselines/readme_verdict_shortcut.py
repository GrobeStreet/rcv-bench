#!/usr/bin/env python3
"""Floor baseline: read the gold verdict straight out of the task README.

`harness/run.py::sanitized_task()` copies `tasks/<id>/README.md` into the
agent-visible directory alongside `claim.json`. Several of those READMEs are
curator notes that state the intended verdict in prose ("Correct verdict: X").

This policy performs NO verification of any kind. It opens README.md, finds
verdict-class tokens, and returns one. It exists to put a number on how much of
RCV-Bench v1 is answerable by reading the task description.
"""
import json
import re
import sys
from pathlib import Path

CLASSES = ["REPRODUCED", "DEVIATION", "FABRICATED", "ROBUST", "FRAGILE"]
TOKEN = re.compile("|".join(CLASSES))  # case-sensitive: the classes are uppercase


def predict(task):
    task_dir = task.get("task_dir")
    readme = Path(task_dir) / "README.md" if task_dir else None
    if not readme or not readme.is_file():
        return "REPRODUCED", "no README.md in sanitized dir", 0.0

    text = readme.read_text(encoding="utf-8", errors="replace")
    hits = [(m.start(), m.group(0)) for m in TOKEN.finditer(text)]
    if not hits:
        return "REPRODUCED", "README.md names no verdict class", 0.0

    # Prefer a class that directly follows the word "verdict"; else the last one.
    verdict_phrase = re.search(r"verdict[^.\n]{0,20}?(" + "|".join(CLASSES) + ")", text, re.IGNORECASE)
    if verdict_phrase:
        return verdict_phrase.group(1), "README.md states the verdict in prose", 1.0
    return hits[-1][1], "README.md names a verdict class", 1.0


def main():
    task = json.load(sys.stdin)
    verdict, why, conf = predict(task)
    json.dump({
        "claim_id": task.get("claim_id"),
        "verdict": verdict,
        "localized_cause": "none",
        "confidence": conf,
        "escalate": False,
        "evidence": ["no verification performed", why],
    }, sys.stdout)


if __name__ == "__main__":
    main()

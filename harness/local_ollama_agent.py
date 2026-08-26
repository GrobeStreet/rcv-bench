#!/usr/bin/env python3
"""Zero-API-cost autonomous RCV-Bench agent using a local Ollama model.

Reads one task JSON from stdin and returns one RCV verdict JSON on stdout.
The model gets a small ReAct-style loop with bounded filesystem/shell tools.
The wrapper deliberately blocks obvious network and parent-directory access so
public benchmark GOLD is not available through the tool surface.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

MODEL = os.environ.get("RCV_LOCAL_MODEL", "qwen2.5-coder:1.5b")
MAX_STEPS = int(os.environ.get("RCV_AGENT_MAX_STEPS", "8"))
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434/api/chat")
MAX_TOOL_CHARS = 12000

BLOCKED = re.compile(
    r"(^|[;&| ])(curl|wget|git|gh|ssh|scp|rsync|nc|ncat|telnet|ftp)\b|"
    r"(^|[;&| ])(find|ls|cat|sed|awk|grep)\s+/(?!tmp/rcv-agent)|"
    r"\.\./|/home/runner/work|GOLD|gold\.json",
    re.I,
)

SYSTEM = r"""You are an autonomous research-claim verification agent being evaluated by RCV-Bench.
You are inside ONE sanitized task workspace. You may inspect the claim, README, staged source checkout, and staged env artifacts. You must investigate rather than trust prose.

Verdicts:
- REPRODUCED: claimed result/artifact is regenerated or independently verified within tolerance.
- DEVIATION: a concrete regenerated/verified result materially disagrees with the claim.
- FABRICATED: the claimed artifact/result has no supporting artifact or executable evidence where one should exist; do not use this merely for an execution failure.
- ROBUST: a declared robustness perturbation preserves the result.
- FRAGILE: the declared robustness perturbation materially breaks/weakens the result.

Use tools to inspect and execute evidence. If evidence is unavailable, escalate rather than inventing it. Never search the web or parent filesystem. Do not inspect GOLD.

At each turn output ONLY one JSON object, either:
{"action":"list_files","path":"."}
{"action":"read_file","path":"relative/path","max_chars":12000}
{"action":"run_shell","command":"safe command scoped to this task"}
or final:
{"final":{"verdict":"REPRODUCED|DEVIATION|FABRICATED|ROBUST|FRAGILE","localized_cause":"...","confidence":0.0,"escalate":false,"evidence":["..."]}}
"""


def ollama(messages):
    body = json.dumps({
        "model": MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0.1, "num_ctx": 8192},
    }).encode()
    req = urllib.request.Request(OLLAMA_URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = json.load(resp)
    return data["message"]["content"].strip()


def extract_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
        raise


def safe_path(root: Path, raw: str) -> Path:
    p = (root / raw).resolve()
    if root != p and root not in p.parents:
        raise ValueError("path escapes task workspace")
    if "GOLD" in p.parts or p.name == "gold.json":
        raise ValueError("gold is forbidden")
    return p


def list_files(root: Path, raw: str):
    p = safe_path(root, raw)
    if not p.exists():
        return "missing path"
    if p.is_file():
        return str(p.relative_to(root))
    rows = []
    for x in sorted(p.iterdir(), key=lambda q: q.name)[:250]:
        if x.name in {".git", "GOLD"}:
            continue
        rows.append(("dir " if x.is_dir() else "file") + " " + str(x.relative_to(root)))
    return "\n".join(rows)


def read_file(root: Path, raw: str, max_chars: int):
    p = safe_path(root, raw)
    if not p.is_file():
        return "not a file"
    data = p.read_text(errors="replace")
    return data[: min(max_chars, MAX_TOOL_CHARS)]


def run_shell(root: Path, command: str):
    if BLOCKED.search(command):
        return "BLOCKED by benchmark sandbox policy"
    # Commands execute only from the sanitized task root. The model does not receive
    # benchmark-root environment variables or a generic filesystem browsing tool.
    env = {
        "PATH": os.environ.get("PATH", ""),
        "HOME": str(root),
        "PYTHONNOUSERSITE": "1",
        "PYTHONPATH": "",
        "OMP_NUM_THREADS": "2",
        "OPENBLAS_NUM_THREADS": "2",
    }
    try:
        p = subprocess.run(
            command,
            shell=True,
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            timeout=180,
        )
        out = f"exit={p.returncode}\nSTDOUT:\n{p.stdout}\nSTDERR:\n{p.stderr}"
        return out[-MAX_TOOL_CHARS:]
    except subprocess.TimeoutExpired:
        return "TIMEOUT after 180 seconds"


def tool_result(root: Path, obj: dict):
    action = obj.get("action")
    if action == "list_files":
        return list_files(root, str(obj.get("path", ".")))
    if action == "read_file":
        return read_file(root, str(obj.get("path", "")), int(obj.get("max_chars", 12000)))
    if action == "run_shell":
        return run_shell(root, str(obj.get("command", "")))
    return "invalid action; use list_files, read_file, run_shell, or final"


def normalize_final(task, final):
    verdict = str(final.get("verdict", "DEVIATION")).upper()
    if verdict not in {"REPRODUCED", "DEVIATION", "FABRICATED", "ROBUST", "FRAGILE"}:
        verdict = "DEVIATION"
    try:
        conf = min(1.0, max(0.0, float(final.get("confidence", 0.3))))
    except Exception:
        conf = 0.3
    ev = final.get("evidence", [])
    if not isinstance(ev, list):
        ev = [str(ev)]
    return {
        "claim_id": task["claim_id"],
        "verdict": verdict,
        "localized_cause": str(final.get("localized_cause", "none")),
        "confidence": conf,
        "escalate": bool(final.get("escalate", False)),
        "evidence": [str(x)[:500] for x in ev[:10]],
        "agent": {"model": MODEL, "max_steps": MAX_STEPS, "tool_policy": "bounded-local-no-network"},
    }


def main():
    task = json.load(sys.stdin)
    root = Path(task["task_dir"]).resolve()
    # Strip the absolute task_dir from model-visible metadata; cwd is enough.
    visible = dict(task)
    visible["task_dir"] = "."
    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": "Investigate this claim. Task JSON:\n" + json.dumps(visible, indent=2)},
    ]
    last_error = None
    for _ in range(MAX_STEPS):
        text = ollama(messages)
        try:
            obj = extract_json(text)
        except Exception as exc:
            last_error = f"invalid model JSON: {exc}"
            messages.append({"role": "assistant", "content": text})
            messages.append({"role": "user", "content": "Your response was invalid. Output exactly one allowed JSON object."})
            continue
        if isinstance(obj, dict) and isinstance(obj.get("final"), dict):
            json.dump(normalize_final(task, obj["final"]), sys.stdout)
            return
        result = tool_result(root, obj if isinstance(obj, dict) else {})
        messages.append({"role": "assistant", "content": json.dumps(obj)})
        messages.append({"role": "user", "content": "TOOL RESULT:\n" + result})

    fallback = {
        "verdict": "DEVIATION",
        "localized_cause": "agent-step-limit",
        "confidence": 0.0,
        "escalate": True,
        "evidence": [last_error or "agent exhausted tool budget without a valid final verdict"],
    }
    json.dump(normalize_final(task, fallback), sys.stdout)


if __name__ == "__main__":
    main()

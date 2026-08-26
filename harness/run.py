#!/usr/bin/env python3
"""RCV-Bench v1 harness — run real agents over hidden-gold task packets.

Three modes are supported:
  --command CMD   external agent process; one task JSON on stdin, one verdict JSON on stdout
  --agent MOD:FN  in-process Python callable (developer convenience)
  --policy NAME   deterministic reference policy

The agent-visible task directory contains claim.json, README.md, and env/ when
present, but never GOLD/. For a serious evaluation, run this harness in an
environment where the agent cannot access the benchmark checkout itself.
"""
from __future__ import annotations

import argparse
import glob
import importlib
import json
import os
import shlex
import shutil
import subprocess
import tempfile
import time

try:
    from agent_protocol import parse_agent_stdout, validate_verdict
except ImportError:
    from harness.agent_protocol import parse_agent_stdout, validate_verdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def task_sources():
    for cj in sorted(glob.glob(os.path.join(ROOT, "tasks", "*", "claim.json"))):
        yield cj


def sanitized_task(cj, tmp_root):
    src_dir = os.path.dirname(cj)
    cid = os.path.basename(src_dir)
    dst_dir = os.path.join(tmp_root, cid)
    os.makedirs(dst_dir, exist_ok=True)
    for name in ("claim.json", "README.md"):
        src = os.path.join(src_dir, name)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(dst_dir, name))
    env_src = os.path.join(src_dir, "env")
    if os.path.isdir(env_src):
        shutil.copytree(env_src, os.path.join(dst_dir, "env"))
    with open(cj) as f:
        claim = json.load(f)
    claim["task_dir"] = dst_dir
    return claim


def resolve_agent(spec):
    mod, _, fn = spec.partition(":")
    return getattr(importlib.import_module(mod), fn or "predict")


def _policy_agent(name):
    if name == "naive_rerun":
        with open(os.path.join(ROOT, "harness", "rerun_observations.json")) as f:
            obs = json.load(f)["observations"]

        def agent(task):
            cid = task["claim_id"]
            if task.get("task_type") == "ROBUST":
                return {"claim_id": cid, "verdict": "REPRODUCED", "localized_cause": "none", "confidence": 0.65, "escalate": False}
            matches = obs[cid]["matches_claim"]
            return {"claim_id": cid, "verdict": "REPRODUCED" if matches else "DEVIATION", "localized_cause": "none" if matches else "value-mismatch", "confidence": 0.75 if matches else 0.60, "escalate": False}
        return agent
    if name == "always_reproduced":
        return lambda task: {"claim_id": task["claim_id"], "verdict": "REPRODUCED", "localized_cause": "none", "confidence": 0.5, "escalate": False}
    raise SystemExit(f"unknown policy '{name}'")


def run_external(command, task, timeout):
    started = time.monotonic()
    proc = subprocess.run(
        shlex.split(command),
        input=json.dumps(task),
        text=True,
        capture_output=True,
        timeout=timeout,
        cwd=task["task_dir"],
        env={**os.environ, "RCV_BENCH_CLAIM_ID": task["claim_id"]},
    )
    elapsed = time.monotonic() - started
    if proc.returncode != 0:
        raise RuntimeError(
            f"agent exited {proc.returncode}; stderr={proc.stderr[-2000:]!r}"
        )
    verdict = parse_agent_stdout(proc.stdout, task["claim_id"])
    return verdict, {"seconds": elapsed, "stderr": proc.stderr[-4000:]}


def failure_verdict(task, exc):
    return {
        "claim_id": task["claim_id"],
        "verdict": "DEVIATION",
        "localized_cause": "agent-error",
        "confidence": 0.0,
        "escalate": True,
        "evidence": [],
        "harness_error": f"{type(exc).__name__}: {exc}",
    }


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--command", help="external agent command; task JSON via stdin, verdict JSON via stdout")
    g.add_argument("--agent", help="Python module:function callable")
    g.add_argument("--policy", choices=["naive_rerun", "always_reproduced"])
    ap.add_argument("--timeout", type=float, default=300.0, help="per-task timeout for --command")
    ap.add_argument("--out", default="predictions.json")
    ap.add_argument("--trace", default=None, help="optional JSONL execution trace path")
    ap.add_argument("--fail-fast", action="store_true")
    args = ap.parse_args()

    agent = None
    if args.policy:
        agent = _policy_agent(args.policy)
    elif args.agent:
        agent = resolve_agent(args.agent)

    preds = []
    trace = []
    with tempfile.TemporaryDirectory(prefix="rcv-bench-agent-") as tmp_root:
        for cj in task_sources():
            task = sanitized_task(cj, tmp_root)
            started = time.monotonic()
            meta = {}
            try:
                if args.command:
                    verdict, meta = run_external(args.command, task, args.timeout)
                else:
                    verdict = validate_verdict(agent(task), task["claim_id"])
                    meta = {"seconds": time.monotonic() - started}
            except Exception as exc:
                if args.fail_fast:
                    raise
                verdict = failure_verdict(task, exc)
                meta = {"seconds": time.monotonic() - started, "error": verdict["harness_error"]}
            preds.append(verdict)
            trace.append({"claim_id": task["claim_id"], **meta})
            print(f"[{len(preds):02d}] {task['claim_id']}: {verdict['verdict']} ({meta.get('seconds', 0):.2f}s)")

    with open(args.out, "w") as f:
        json.dump(preds, f, indent=2)
    if args.trace:
        with open(args.trace, "w") as f:
            for row in trace:
                f.write(json.dumps(row) + "\n")
    mode = args.command or args.agent or args.policy
    print(f"ran {mode!r} over {len(preds)} tasks -> {args.out}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""RCV-Bench v1 harness — run real agents over hidden-gold task packets.

Three modes are supported:
  --command CMD   external agent process; one task JSON on stdin, one verdict JSON on stdout
  --agent MOD:FN  in-process Python callable (developer convenience)
  --policy NAME   deterministic reference policy

The agent-visible task directory contains claim.json, README.md, env/ when
present, and (with --stage-source) a pinned source checkout, but never GOLD/.
For a serious evaluation, run the agent in an environment where it cannot access
the benchmark checkout itself.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import importlib
import json
import os
import re
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
GITHUB_RE = re.compile(r"https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)")


def task_sources(include=None):
    wanted = set(include or [])
    for cj in sorted(glob.glob(os.path.join(ROOT, "tasks", "*", "claim.json"))):
        cid = os.path.basename(os.path.dirname(cj))
        if wanted and cid not in wanted:
            continue
        yield cj


def _source_url(claim):
    raw = str(claim.get("source", ""))
    m = GITHUB_RE.search(raw)
    if not m:
        return None
    owner, repo = m.groups()
    return f"https://github.com/{owner}/{repo}.git"


def _cache_key(url, pin):
    return hashlib.sha256(f"{url}@{pin}".encode()).hexdigest()[:16]


def stage_source_checkout(claim, dst_dir, cache_root):
    """Clone the declared source and freeze it at the declared pin before agent execution.

    This setup step may use network access. The agent process itself can then be run
    with network disabled. Failures are recorded rather than silently ignored.
    """
    url = _source_url(claim)
    pin = str(claim.get("pin") or "").strip()
    provenance = {
        "declared_source": claim.get("source"),
        "declared_pin": pin,
        "staged": False,
    }
    if not url or not pin:
        provenance["error"] = "source URL or pin could not be parsed"
        with open(os.path.join(dst_dir, "SOURCE_PROVENANCE.json"), "w") as f:
            json.dump(provenance, f, indent=2)
        return provenance

    cache = os.path.join(cache_root, _cache_key(url, pin))
    try:
        if not os.path.isdir(os.path.join(cache, ".git")):
            subprocess.run(
                ["git", "clone", "--quiet", "--no-checkout", url, cache],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=180,
            )
            subprocess.run(
                ["git", "-C", cache, "checkout", "--quiet", pin],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=120,
            )
        head = subprocess.check_output(
            ["git", "-C", cache, "rev-parse", "HEAD"], text=True
        ).strip()
        source_dst = os.path.join(dst_dir, "source")
        shutil.copytree(cache, source_dst)
        provenance.update({
            "staged": True,
            "resolved_url": url,
            "resolved_head": head,
            "source_dir": "source",
        })
        claim["source_dir"] = "source"
    except Exception as exc:
        provenance["error"] = f"{type(exc).__name__}: {exc}"

    with open(os.path.join(dst_dir, "SOURCE_PROVENANCE.json"), "w") as f:
        json.dump(provenance, f, indent=2)
    return provenance


def sanitized_task(cj, tmp_root, stage_source=False):
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
    if stage_source:
        cache_root = os.path.join(tmp_root, "_source_cache")
        os.makedirs(cache_root, exist_ok=True)
        stage_source_checkout(claim, dst_dir, cache_root)
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
    ap.add_argument("--timeout", type=float, default=900.0, help="per-task timeout for --command")
    ap.add_argument("--out", default="predictions.json")
    ap.add_argument("--trace", default=None, help="optional JSONL execution trace path")
    ap.add_argument("--fail-fast", action="store_true")
    ap.add_argument("--stage-source", action="store_true", help="pre-clone declared source at declared pin into task_dir/source")
    ap.add_argument("--include", nargs="*", default=None, help="optional claim IDs to run")
    args = ap.parse_args()

    agent = None
    if args.policy:
        agent = _policy_agent(args.policy)
    elif args.agent:
        agent = resolve_agent(args.agent)

    preds = []
    trace = []
    with tempfile.TemporaryDirectory(prefix="rcv-bench-agent-") as tmp_root:
        for cj in task_sources(args.include):
            task = sanitized_task(cj, tmp_root, stage_source=args.stage_source)
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

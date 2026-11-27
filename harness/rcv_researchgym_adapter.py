#!/usr/bin/env python3
"""RCV-Bench <-> ResearchGym interoperability adapter.

Exposes a ResearchGym-style autonomous research agent as an RCV-Bench v1
external agent. Implements the RCV-Bench process contract exactly: one task
JSON on stdin, exactly one verdict JSON on stdout, no prose on stdout.

Why an adapter is needed
------------------------
The two frameworks have incompatible agent contracts:

  ResearchGym : the agent receives a task DIRECTORY (task_description.md +
                grading/grade.sh + baseline scores) and runs autonomously for
                12-24h to MAXIMISE A NUMERIC SCORE. Its output is a workspace
                graded by a shell script.
  RCV-Bench   : the agent receives a CLAIM PACKET and must return a BOUNDED
                STRUCTURED VERDICT drawn from a fixed class set, with
                calibrated confidence, a localised cause, and evidence.

Bridging therefore requires two translations, both implemented here:

  1. claim packet          -> ResearchGym-style task directory   build_rg_task()
  2. free-form agent run   -> structured RCV-Bench verdict        extract_verdict()

Translation (2) is the hard half: a ResearchGym agent has no notion of a
verdict, so the task description instructs it to terminate by emitting a
machine-readable block, which this adapter parses.

Backends
--------
  mock     Offline, zero cost. Exercises BOTH translations and the full
           process contract with no model call. This is a PROTOCOL
           CONFORMANCE harness, NOT a capability claim: its policy is
           deliberately non-inferential, so its score reflects the floor
           by construction and must never be reported as agent performance.
  rgagent  Real ResearchGym RGAgent via run_agent.py. Requires `uv`,
           Python >= 3.12, a ResearchGym checkout and a provider API key.
           Missing prerequisites raise loudly rather than degrading silently.

Usage (from the RCV-Bench repo root):

  python3 harness/run.py \
    --command "python3 $PWD/harness/rcv_researchgym_adapter.py --backend mock" \
    --out predictions_researchgym_mock.json \
    --trace trace_researchgym_mock.jsonl

  python3 scoring/score.py predictions_researchgym_mock.json --name rg-mock-interop
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

VALID_VERDICTS = {"REPRODUCED", "DEVIATION", "FABRICATED", "ROBUST", "FRAGILE"}

# The terminal contract we impose on a free-form ResearchGym agent so that its
# run can be reduced to an RCV-Bench verdict.
VERDICT_OPEN = "<RCV_VERDICT>"
VERDICT_CLOSE = "</RCV_VERDICT>"


def log(msg: str) -> None:
    """Diagnostics go to stderr. stdout is reserved for the single verdict JSON."""
    print(msg, file=sys.stderr)


# ---------------------------------------------------------------------------
# Translation 1: RCV-Bench claim packet -> ResearchGym-style task directory
# ---------------------------------------------------------------------------

TASK_DESCRIPTION_TEMPLATE = """# Research Goal

Determine whether the claimed research result below is actually supported by
its code and evidence. This is a verification task, not a score-maximisation
task: re-executing the entrypoint is necessary but not sufficient.

## Claim under test

- claim_id: `{claim_id}`
- source repository: {source}
- pinned commit: {pin}
- task type: {task_type}
- declared entrypoint: `{entrypoint}`
- claimed value: {claimed_value}
- metric: {metric}
- tolerance: {tolerance}

{perturbation_section}

## Working directory

The sanitized task directory has been copied to `input/`. It contains the claim
packet and any provided environment, and deliberately does NOT contain the
answer key. Do not attempt to read any parent benchmark checkout, and do not
search the public internet for this benchmark's gold labels: either action
invalidates the run.

## Experimental Settings

Work only from the materials in `input/`. You may execute code, inspect files,
and regenerate the claimed value. Declare any step you could not complete.

## Evaluation Metrics

You are scored on classification quality, not on improving a number:

- verdict accuracy and macro-F1 over the verdict classes
- recall on the FRAGILE and FABRICATED classes
- correctness of the localised cause
- calibration of your stated confidence (Brier score)

Allowed verdicts: REPRODUCED, DEVIATION, FABRICATED, ROBUST, FRAGILE.

- REPRODUCED - the claimed value regenerates within tolerance.
- DEVIATION  - it regenerates to a materially different value.
- FABRICATED - the claimed support is missing or cannot exist as described.
- ROBUST     - the declared perturbation does not break the result.
- FRAGILE    - the declared perturbation does break the result.

## Required termination

You MUST end your run by printing exactly one block in this form, and nothing
after it:

{open_tag}
{{"verdict": "<one of the allowed verdicts>",
  "regenerated_value": <number or null>,
  "delta_vs_claim": <number or null>,
  "localized_cause": "<short slug, or 'none'>",
  "confidence": <float in [0,1]>,
  "escalate": <true|false>,
  "evidence": ["<short factual observation>", "..."]}}
{close_tag}

A run that does not emit this block cannot be scored and counts as an error.
"""

PERTURBATION_TEMPLATE = """## Declared robustness condition

The claim declares a perturbation that must be probed before answering:

- kind: {kind}
- specification: {spec}

If the result survives this perturbation the verdict is ROBUST; if it does not,
the verdict is FRAGILE. Simply re-running the headline number does not answer
this question.
"""

GRADE_STUB = """#!/usr/bin/env bash
# RCV-Bench scores classification quality from the returned verdict JSON, not a
# numeric submission. ResearchGym's grade.sh contract has no equivalent, so this
# stub exists only to satisfy the ResearchGym task layout. The authoritative
# scoring path is: rcv-bench/scoring/score.py over harness predictions.
echo '{"score": null, "note": "scored externally by rcv-bench/scoring/score.py"}'
"""


def build_rg_task(task: dict, work_root: Path) -> Path:
    """Materialise a ResearchGym-shaped task directory from an RCV claim packet."""
    claim_id = task["claim_id"]
    rg_task = work_root / f"rcv-{claim_id}"
    (rg_task / "grading").mkdir(parents=True, exist_ok=True)

    perturbation = task.get("perturbation")
    if perturbation:
        perturbation_section = PERTURBATION_TEMPLATE.format(
            kind=perturbation.get("kind", "unspecified"),
            spec=json.dumps(perturbation, indent=2),
        )
    else:
        perturbation_section = ""

    description = TASK_DESCRIPTION_TEMPLATE.format(
        claim_id=claim_id,
        source=task.get("source", "unspecified"),
        pin=task.get("pin", "unspecified"),
        task_type=task.get("task_type", "unspecified"),
        entrypoint=task.get("entrypoint", "unspecified"),
        claimed_value=json.dumps(task.get("claimed_value")),
        metric=task.get("metric", "unspecified"),
        tolerance=json.dumps(task.get("tolerance")),
        perturbation_section=perturbation_section,
        open_tag=VERDICT_OPEN,
        close_tag=VERDICT_CLOSE,
    )
    (rg_task / "task_description.md").write_text(description, encoding="utf-8")

    grade = rg_task / "grading" / "grade.sh"
    grade.write_text(GRADE_STUB, encoding="utf-8")
    grade.chmod(0o755)

    # ResearchGym agents expect their materials under the task dir. Copy the
    # sanitized packet; GOLD/ is already withheld by the RCV-Bench harness.
    src = task.get("task_dir")
    dst = rg_task / "input"
    if src and Path(src).is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst)
    else:
        dst.mkdir(exist_ok=True)
        (dst / "claim.json").write_text(json.dumps(task, indent=2), encoding="utf-8")

    return rg_task


# ---------------------------------------------------------------------------
# Translation 2: free-form agent transcript -> structured RCV-Bench verdict
# ---------------------------------------------------------------------------


def extract_verdict(transcript: str) -> dict:
    """Pull the machine-readable verdict block out of an agent transcript."""
    start = transcript.rfind(VERDICT_OPEN)
    if start == -1:
        raise ValueError("agent transcript contained no %s block" % VERDICT_OPEN)
    end = transcript.find(VERDICT_CLOSE, start)
    if end == -1:
        raise ValueError("agent transcript had an unterminated %s block" % VERDICT_OPEN)
    payload = transcript[start + len(VERDICT_OPEN):end].strip()
    try:
        return json.loads(payload)
    except json.JSONDecodeError as exc:
        raise ValueError(f"verdict block was not valid JSON: {exc}") from exc


def validate_verdict(verdict: dict, claim_id: str) -> dict:
    """Enforce the RCV-Bench response schema. Errors surface, never silently fixed."""
    if not isinstance(verdict, dict):
        raise ValueError("verdict payload was not a JSON object")

    v = verdict.get("verdict")
    if v not in VALID_VERDICTS:
        raise ValueError(f"verdict {v!r} is not one of {sorted(VALID_VERDICTS)}")

    confidence = verdict.get("confidence", 0.0)
    if not isinstance(confidence, (int, float)) or not 0.0 <= float(confidence) <= 1.0:
        raise ValueError(f"confidence {confidence!r} is not a float in [0, 1]")

    evidence = verdict.get("evidence", [])
    if not isinstance(evidence, list):
        raise ValueError("evidence must be a JSON list")

    out = {
        "claim_id": claim_id,
        "verdict": v,
        "regenerated_value": verdict.get("regenerated_value"),
        "delta_vs_claim": verdict.get("delta_vs_claim"),
        "localized_cause": verdict.get("localized_cause", "none"),
        "confidence": float(confidence),
        "escalate": bool(verdict.get("escalate", False)),
        "evidence": evidence,
    }
    return out


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------


def run_mock(task: dict, rg_task: Path) -> str:
    """Offline protocol-conformance backend. Emits no capability claim.

    The policy is deliberately NON-INFERENTIAL: it reports what it could
    actually observe about the translated task and returns a low-confidence
    REPRODUCED with escalate=true. It must never be presented as agent skill.
    It exists to prove that a ResearchGym-shaped task, produced by translation
    1, round-trips through translation 2 and the RCV-Bench process contract.
    """
    description = (rg_task / "task_description.md").read_text(encoding="utf-8")
    materials = sorted(p.name for p in (rg_task / "input").iterdir())

    observations = [
        f"translated claim into ResearchGym task dir ({len(description)} chars)",
        f"sanitized materials visible: {materials}",
        f"declared perturbation present: {bool(task.get('perturbation'))}",
        "offline mock backend: no model call, no verification performed",
    ]
    payload = {
        "verdict": "REPRODUCED",
        "regenerated_value": None,
        "delta_vs_claim": None,
        "localized_cause": "none",
        "confidence": 0.3,
        "escalate": True,
        "evidence": observations,
    }
    # Simulate an agent transcript so the extraction path is genuinely exercised.
    return (
        "[mock backend] inspected translated ResearchGym task.\n"
        f"{VERDICT_OPEN}\n{json.dumps(payload)}\n{VERDICT_CLOSE}\n"
    )


def _latest_run_dir(rg_root: Path):
    """Newest ResearchGym run directory, i.e. runs/<YYYY-MM-DD>/<run_id>/."""
    runs = rg_root / "runs"
    if not runs.is_dir():
        return None
    candidates = [p for p in runs.glob("*/*") if p.is_dir()]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def _read_agent_transcript(run_dir: Path) -> str:
    """Read the PERSISTED agent output.

    ResearchGym redirects the agent process's output into the run directory and
    persists its transcript there; `run_agent.py` itself prints only
    orchestration messages, so parsing the CLI's stdout never sees the verdict
    block.

    Locations are taken from ResearchGym's own `plan.json` (`RG_TRANSCRIPT_PATH`
    and `RG_LOG_DIR`) rather than guessed, so this keeps working if the upstream
    layout changes.
    """
    candidates = []
    plan = run_dir / "plan.json"
    if plan.is_file():
        try:
            env = json.loads(plan.read_text(encoding="utf-8"))["agent"]["env"]
        except (KeyError, json.JSONDecodeError) as exc:
            raise RuntimeError(f"could not read agent env from {plan}: {exc}") from exc
        if env.get("RG_TRANSCRIPT_PATH"):
            candidates.append(Path(env["RG_TRANSCRIPT_PATH"]))
        if env.get("RG_LOG_DIR"):
            log_dir = Path(env["RG_LOG_DIR"])
            candidates += [log_dir / "exec.stdout.log", log_dir / "agent.log"]
    # Documented fallbacks if plan.json is absent or incomplete.
    candidates += [
        run_dir / "transcript.json",
        run_dir / "agent.log",
        run_dir / "logs" / "exec.stdout.log",
    ]

    parts = []
    seen = set()
    for f in candidates:
        if f in seen or not f.is_file():
            continue
        seen.add(f)
        parts.append(f.read_text(encoding="utf-8", errors="replace"))
    if not parts:
        looked = ", ".join(str(c) for c in candidates)
        raise RuntimeError(f"no agent transcript found. looked in: {looked}")
    return "\n".join(parts)


def run_rgagent(
    rg_task: Path,
    model: str,
    hours: float,
    runtime: str,
    image: str | None,
    dry_run: bool,
):
    """Real ResearchGym RGAgent backend. Fails loudly on missing prerequisites.

    Returns the persisted agent transcript, or None for a dry run (which is a
    planning aid and deliberately emits no verdict).
    """
    rg_root_env = os.environ.get("RESEARCHGYM_ROOT")
    if not rg_root_env:
        raise RuntimeError(
            "RESEARCHGYM_ROOT is not set; point it at a ResearchGym checkout"
        )
    rg_root = Path(rg_root_env)
    runner = rg_root / "run_agent.py"
    if not runner.is_file():
        raise RuntimeError(f"run_agent.py not found under RESEARCHGYM_ROOT={rg_root}")
    if runtime == "uv" and shutil.which("uv") is None:
        raise RuntimeError("ResearchGym's uv runtime requires `uv` on PATH")
    if runtime == "docker":
        if shutil.which("docker") is None:
            raise RuntimeError("--runtime docker requires `docker` on PATH")
        if not image:
            raise RuntimeError("--runtime docker requires --image (e.g. researchgym-rg-agent:latest)")
    if not dry_run and not any(
        os.environ.get(k)
        for k in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "GEMINI_API_KEY")
    ):
        # A dry run plans only and makes no model calls, so it needs no key.
        raise RuntimeError(
            "no provider API key in environment; a live RGAgent run bills real money"
        )

    cmd = [
        sys.executable,
        str(runner),
        str(rg_task),
        "rg-agent",
        "--runtime",
        runtime,
        "--model",
        model,
        "--basic_hours",
        str(hours),
    ]
    if runtime == "docker":
        cmd += ["--image", image]
    if dry_run:
        # Forward ResearchGym's own planning mode and stop before verdict
        # extraction: a dry run produces no agent output to parse.
        cmd.append("--dry_run")
        log("[rgagent] dry run, plan only: " + " ".join(cmd))
        proc = subprocess.run(cmd, capture_output=True, text=True, cwd=rg_root)
        log(proc.stdout.strip() or "(no plan output)")
        if proc.returncode != 0:
            raise RuntimeError(
                f"ResearchGym dry run exited {proc.returncode}: {proc.stderr[-2000:]}"
            )
        return None

    log("[rgagent] executing: " + " ".join(cmd))
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=rg_root)
    if proc.returncode != 0:
        raise RuntimeError(
            f"ResearchGym run_agent.py exited {proc.returncode}: {proc.stderr[-2000:]}"
        )

    run_dir = _latest_run_dir(rg_root)
    if run_dir is None:
        raise RuntimeError(f"no ResearchGym run directory produced under {rg_root}/runs")
    log(f"[rgagent] reading persisted transcript from {run_dir}")
    return _read_agent_transcript(run_dir)


# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--backend", choices=["mock", "rgagent"], default="mock")
    ap.add_argument("--model", default="openai/gpt-5")
    ap.add_argument("--hours", type=float, default=0.5)
    ap.add_argument(
        "--runtime",
        choices=["uv", "docker"],
        default="uv",
        help="ResearchGym runtime; publishable runs require docker isolation",
    )
    ap.add_argument(
        "--image", default=None, help="container image, required with --runtime docker"
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="print the ResearchGym plan and exit; standalone only, never through "
        "harness/run.py, because a dry run emits no verdict by design",
    )
    ap.add_argument(
        "--work-root",
        default=None,
        help="where translated ResearchGym task dirs are written (default: temp dir)",
    )
    args = ap.parse_args()

    task = json.load(sys.stdin)
    claim_id = task.get("claim_id")
    if not claim_id:
        raise ValueError("task packet had no claim_id")

    work_root = (
        Path(args.work_root) if args.work_root else Path(tempfile.mkdtemp(prefix="rcv-rg-"))
    )
    work_root.mkdir(parents=True, exist_ok=True)
    rg_task = build_rg_task(task, work_root)
    log(f"[adapter] {claim_id}: translated to ResearchGym task at {rg_task}")

    if args.backend == "mock":
        transcript = run_mock(task, rg_task)
    else:
        transcript = run_rgagent(
            rg_task, args.model, args.hours, args.runtime, args.image, args.dry_run
        )
        if transcript is None:
            log("[adapter] dry run complete; no verdict emitted by design")
            return 0

    verdict = validate_verdict(extract_verdict(transcript), claim_id)

    # Exactly one JSON object on stdout, nothing else.
    json.dump(verdict, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

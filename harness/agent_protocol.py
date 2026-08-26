#!/usr/bin/env python3
"""RCV-Bench v1 external-agent protocol helpers.

The benchmark communicates with a real agent over a process boundary. The agent
receives one JSON task object on stdin and must print exactly one JSON verdict
object on stdout. GOLD/ is never copied into the agent-visible task directory.
"""
from __future__ import annotations

import json
from typing import Any

ALLOWED_VERDICTS = {"REPRODUCED", "DEVIATION", "FABRICATED", "ROBUST", "FRAGILE"}


class VerdictError(ValueError):
    """Raised when an agent returns an invalid verdict payload."""


def validate_verdict(payload: Any, claim_id: str) -> dict:
    if not isinstance(payload, dict):
        raise VerdictError("agent output must be a JSON object")

    verdict = payload.get("verdict")
    if verdict not in ALLOWED_VERDICTS:
        raise VerdictError(
            f"verdict must be one of {sorted(ALLOWED_VERDICTS)}; got {verdict!r}"
        )

    out = dict(payload)
    out["claim_id"] = claim_id

    confidence = float(out.get("confidence", 0.5))
    if not 0.0 <= confidence <= 1.0:
        raise VerdictError("confidence must be between 0 and 1")
    out["confidence"] = confidence

    out["escalate"] = bool(out.get("escalate", False))
    out.setdefault("localized_cause", "none")
    out.setdefault("evidence", [])
    if not isinstance(out["evidence"], list):
        raise VerdictError("evidence must be a JSON list")

    return out


def parse_agent_stdout(stdout: str, claim_id: str) -> dict:
    text = stdout.strip()
    if not text:
        raise VerdictError("agent produced empty stdout")
    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise VerdictError(
            "agent stdout must contain exactly one JSON object and no prose"
        ) from exc
    return validate_verdict(payload, claim_id)

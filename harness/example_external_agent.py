#!/usr/bin/env python3
"""Minimal external-agent example for the RCV-Bench v1 process protocol.

This is deliberately weak: it demonstrates the I/O contract, not a competitive
agent. Replace its policy with any CLI-capable coding/research agent.
"""
import json
import sys


def main():
    task = json.load(sys.stdin)
    verdict = {
        "claim_id": task["claim_id"],
        "verdict": "REPRODUCED",
        "localized_cause": "none",
        "confidence": 0.5,
        "escalate": False,
        "evidence": ["protocol-smoke-test"],
    }
    json.dump(verdict, sys.stdout)


if __name__ == "__main__":
    main()

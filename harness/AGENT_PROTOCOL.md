# RCV-Bench v1 agent-under-test protocol

RCV-Bench v1 can evaluate a real CLI-capable agent through a process boundary.
The benchmark gives the agent a sanitized task packet and withholds `GOLD/`.

## Contract

For every task, `harness/run.py` starts the configured command with its working
directory set to the sanitized task directory.

The command receives one JSON object on **stdin**. It is the task's `claim.json`
plus a temporary `task_dir` path. That directory contains only:

- `claim.json`
- `README.md`
- `env/` when the task provides one

The command must emit **exactly one JSON object on stdout** and no prose.

Required field:

```json
{"verdict":"REPRODUCED"}
```

Allowed verdicts are:

- `REPRODUCED`
- `DEVIATION`
- `FABRICATED`
- `ROBUST`
- `FRAGILE`

Recommended full response:

```json
{
  "verdict": "FRAGILE",
  "regenerated_value": 2.75,
  "delta_vs_claim": 0.0,
  "localized_cause": "lrg2-deletion",
  "confidence": 0.91,
  "escalate": false,
  "evidence": ["reproduced headline", "declared perturbation changes result"]
}
```

`confidence` must be in `[0, 1]`. `evidence` must be a JSON list. The harness
sets the authoritative `claim_id` from the task packet.

## Smoke test

```bash
python3 harness/run.py \
  --command "python3 /absolute/path/to/rcv-bench/harness/example_external_agent.py" \
  --out predictions_external.json \
  --trace trace.jsonl

python3 scoring/score.py predictions_external.json --name external-smoke-test
```

The example is intentionally an always-REPRODUCED policy. Its purpose is to
prove the external process protocol, not benchmark performance.

## Plugging in a real agent

Any agent is eligible if it can be exposed as a command that:

1. reads the task JSON from stdin;
2. inspects/executes files inside `task_dir` as needed;
3. performs its own reasoning/tool loop;
4. prints the verdict JSON to stdout.

A thin adapter can therefore wrap a local model, coding-agent CLI, containerized
agent, or a provider-backed research agent without changing RCV-Bench itself.
Provider credentials and inference costs are intentionally outside the benchmark.

## Gold isolation and evaluation integrity

The sanitized directory does not contain `GOLD/`, but this alone is not a hard
security boundary. An agent with unrestricted filesystem access could inspect the
parent benchmark checkout and leak gold.

For publishable scores, run the agent in a separate container/VM whose mounted
input is only the sanitized task directory, with the scorer and gold retained on
the host. Network access should be declared because it changes the evaluation
condition. Record agent/model version, command/container digest, network policy,
time limit, and any tool permissions with every submitted score.

## Failure semantics

By default, a crash, timeout, malformed stdout, or invalid verdict becomes an
`agent-error` prediction with `confidence=0` and `escalate=true`, allowing a full
benchmark run to finish. Use `--fail-fast` while developing adapters.

`--trace trace.jsonl` records per-task runtime and bounded stderr for auditability.

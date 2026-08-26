#!/usr/bin/env python3
"""RCV-Bench MMLU live harness (v1) — BATCHED reproduction of mmlu-robustness-audit's
audit_full.py. Same model/dataset pins, same raw-completion prompt, same A/B/C/D
next-token scoring and cyclic-rotation protocol, but scores prompts in padded batches
so it runs end-to-end on CPU in minutes instead of ~50 min. Math is identical to the
serial harness (per-sequence last-token logits over the four label tokens).

Outputs the same parquet schema audit_full.py writes, so mmlu-robustness-audit/analyze.py
consumes it unchanged. Run from inside the cloned mmlu-robustness-audit repo (needs audit_utils)."""
from __future__ import annotations
import argparse, json, os, random, sys
from pathlib import Path
import numpy as np, pandas as pd, torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from datasets import load_dataset
from audit_utils import inverse_map_prediction, rotate_answer_index, rotate_choices, top_diagnostics

LABELS = ["A", "B", "C", "D"]
MODEL = "Qwen/Qwen2.5-0.5B-Instruct"
MODEL_REV = "7ae557604adf67be50417f59c2c2f167def9a775"
DS = "cais/mmlu"; DS_REV = "c30699e8356da336a370243923dbaf21066bb9fe"

def format_prompt(q, choices):
    lines = [q.strip(), ""] + [f"{l}. {c}" for l, c in zip(LABELS, choices)] + ["", "Answer:"]
    return "\n".join(lines)

def label_token_ids(tok):
    ids = []
    for label in LABELS:
        spaced = tok.encode(" " + label, add_special_tokens=False)
        cand = tok.encode(label, add_special_tokens=False)
        t = spaced if len(spaced) == 1 else cand
        if len(t) != 1: raise ValueError(f"{label} not single token")
        ids.append(t[0])
    return ids

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--dtype", default="float32", choices=["float32", "bfloat16"])
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--out", default="/tmp/mmlu-live.parquet")
    a = ap.parse_args()
    random.seed(a.seed); np.random.seed(a.seed); torch.manual_seed(a.seed)
    torch.set_num_threads(max(1, os.cpu_count() or 2))

    ds = load_dataset(DS, "all", split="test", revision=DS_REV)
    idxs = list(range(len(ds))); random.Random(a.seed).shuffle(idxs); idxs = idxs[:a.n]

    tok = AutoTokenizer.from_pretrained(MODEL, revision=MODEL_REV, use_fast=True)
    if tok.pad_token is None: tok.pad_token = tok.eos_token
    tok.padding_side = "left"  # so last position is the real final token for every row
    dt = torch.float32 if a.dtype == "float32" else torch.bfloat16
    model = AutoModelForCausalLM.from_pretrained(MODEL, revision=MODEL_REV, torch_dtype=dt)
    model.eval()
    tids = label_token_ids(tok)

    # build all (q_rank, idx, rotation) work items
    work = []
    for q_rank, idx in enumerate(idxs):
        it = ds[idx]; q = it["question"]; ch = list(it["choices"]); ans = int(it["answer"])
        subj = it.get("subject", "")
        for r in range(4):
            rot = rotate_choices(ch, r)
            work.append((q_rank, idx, subj, r, ans, rotate_answer_index(ans, r), format_prompt(q, rot)))

    rows = []
    B = a.batch_size
    for s in range(0, len(work), B):
        chunk = work[s:s+B]
        prompts = [w[6] for w in chunk]
        enc = tok(prompts, return_tensors="pt", padding=True)
        with torch.no_grad():
            try:
                out = model(**enc, logits_to_keep=1)     # only last position -> [B,1,V], avoids OOM
            except TypeError:
                out = model(**enc, num_logits_to_keep=1)
        last = out.logits[:, -1, :]                 # left-padded -> real last token
        sel = last[:, tids]                          # [B, 4]
        probs = torch.softmax(sel.float(), dim=1).cpu().numpy()
        for (q_rank, idx, subj, r, ans, ans_disp, _p), pr in zip(chunk, probs):
            pred_disp = int(np.argmax(pr)); diag = top_diagnostics(pr.tolist())
            pred_und = inverse_map_prediction(pred_disp, r)
            rows.append({
                "question_rank": q_rank, "dataset_index": idx, "subject": subj, "rotation": r,
                "answer_underlying": ans, "answer_display": ans_disp,
                "pred_display": pred_disp, "pred_underlying": pred_und,
                "correct": int(pred_und == ans), "confidence": float(pr[pred_disp]),
                "prob_A": float(pr[0]), "prob_B": float(pr[1]), "prob_C": float(pr[2]), "prob_D": float(pr[3]),
                "top1_probability": diag["top1_probability"], "top2_probability": diag["top2_probability"],
                "top1_top2_margin": diag["top1_top2_margin"], "top_tie_count": diag["top_tie_count"],
                "top_exact_tie": diag["top_exact_tie"],
                "top_tie_indices": ",".join(map(str, diag["top_tie_indices"])),
                "label_entropy": diag["label_entropy"], "rotation_dtype": a.dtype,
            })
        print(f"  {min(s+B,len(work))}/{len(work)} prompts", flush=True)

    pd.DataFrame(rows).to_parquet(a.out, index=False)
    print(f"wrote {len(rows)} predictions -> {a.out}")

if __name__ == "__main__":
    main()

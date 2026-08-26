#!/usr/bin/env python3
"""RCV-Bench v0 scorer. Compares a predictions file to the scoring GOLD verdicts and
reports the multi-factor rubric: verdict accuracy, macro-F1 over the 5 classes,
per-class P/R/F1, FRAGILE recall + FABRICATED recall (the headroom classes),
localization accuracy on planted defects, escalation P/R, and Brier calibration.

Usage: python3 scoring/score.py baselines/predictions_naive_rerun.json [--name naive-rerun]
"""
import json, glob, os, sys, math

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLASSES = ["REPRODUCED", "DEVIATION", "FABRICATED", "ROBUST", "FRAGILE"]

def load_gold():
    gold = {}
    for gj in glob.glob(os.path.join(ROOT, "tasks", "*", "GOLD", "gold.json")):
        cid = os.path.basename(os.path.dirname(os.path.dirname(gj)))
        gold[cid] = json.load(open(gj))
    return gold

def macro_f1(pairs):
    f1s = {}
    for c in CLASSES:
        tp = sum(1 for g, p in pairs if g == c and p == c)
        fp = sum(1 for g, p in pairs if g != c and p == c)
        fn = sum(1 for g, p in pairs if g == c and p != c)
        prec = tp / (tp + fp) if tp + fp else 0.0
        rec = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
        support = sum(1 for g, _ in pairs if g == c)
        f1s[c] = {"precision": prec, "recall": rec, "f1": f1, "support": support}
    present = [c for c in CLASSES if f1s[c]["support"] > 0]
    macro = sum(f1s[c]["f1"] for c in present) / len(present) if present else 0.0
    return macro, f1s

def main():
    if len(sys.argv) < 2:
        print("usage: score.py <predictions.json> [--name NAME]"); sys.exit(1)
    pred_path = sys.argv[1]
    name = sys.argv[sys.argv.index("--name") + 1] if "--name" in sys.argv else os.path.basename(pred_path)
    preds = {p["claim_id"]: p for p in json.load(open(pred_path))}
    gold = load_gold()

    pairs, rows = [], []
    correct = 0
    brier_terms = []
    loc_total = loc_correct = 0
    for cid in sorted(gold):
        g = gold[cid]; p = preds.get(cid, {})
        gv, pv = g["verdict"], p.get("verdict", "MISSING")
        ok = (gv == pv); correct += ok
        pairs.append((gv, pv))
        conf = float(p.get("confidence", 0.5))
        brier_terms.append((conf - (1.0 if ok else 0.0)) ** 2)
        # localization only graded where gold has a real cause (planted or mismatch)
        gcause = g.get("localized_cause", "none")
        if gcause not in ("none", None):
            loc_total += 1
            loc_correct += int(p.get("localized_cause") == gcause)
        rows.append((cid, gv, pv, "OK" if ok else "X", conf))

    n = len(gold)
    acc = correct / n
    macro, f1s = macro_f1(pairs)
    brier = sum(brier_terms) / n
    frag_rec = f1s["FRAGILE"]["recall"]
    fab_rec = f1s["FABRICATED"]["recall"]
    # escalation P/R (gold escalate flags)
    esc_tp = sum(1 for cid in gold if gold[cid].get("escalate") and preds.get(cid, {}).get("escalate"))
    esc_fp = sum(1 for cid in gold if not gold[cid].get("escalate") and preds.get(cid, {}).get("escalate"))
    esc_fn = sum(1 for cid in gold if gold[cid].get("escalate") and not preds.get(cid, {}).get("escalate"))

    print(f"\n=== RCV-Bench v0 score: {name} ===")
    print(f"instances: {n}")
    print(f"verdict accuracy:      {acc:.3f}  ({correct}/{n})")
    print(f"macro-F1 (5 classes):  {macro:.3f}")
    print(f"FRAGILE recall:        {frag_rec:.3f}   <- robustness blind-spot")
    print(f"FABRICATED recall:     {fab_rec:.3f}   <- fabrication blind-spot")
    print(f"localization acc:      {(loc_correct/loc_total if loc_total else float('nan')):.3f}  ({loc_correct}/{loc_total} defect cases)")
    print(f"escalation P/R:        {('n/a (no gold escalations)' if (esc_tp+esc_fn)==0 else f'{esc_tp}/{esc_tp+esc_fp} , {esc_tp}/{esc_tp+esc_fn}')}")
    print(f"Brier (confidence):    {brier:.3f}   (lower=better calibrated)")
    print("\nper-class F1:")
    for c in CLASSES:
        s = f1s[c]
        if s["support"]:
            print(f"  {c:<11} P={s['precision']:.2f} R={s['recall']:.2f} F1={s['f1']:.2f} (n={s['support']})")
    print("\nper-instance:")
    for cid, gv, pv, mark, conf in rows:
        print(f"  [{mark}] {cid:<24} gold={gv:<11} pred={pv:<11} conf={conf:.2f}")
    return {"name": name, "n": n, "accuracy": acc, "macro_f1": macro,
            "fragile_recall": frag_rec, "fabricated_recall": fab_rec, "brier": brier}

if __name__ == "__main__":
    main()

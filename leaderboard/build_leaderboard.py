#!/usr/bin/env python3
"""Generate leaderboard/index.html from INDEX.json + gold + baseline predictions,
so the page can never drift from the scored numbers. Self-contained, theme-aware."""
import json, glob, os, html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLASSES = ["REPRODUCED", "DEVIATION", "FABRICATED", "ROBUST", "FRAGILE"]
CHIP = {"REPRODUCED": "#2e7d5b", "DEVIATION": "#b5820a", "FABRICATED": "#b23b3b", "FRAGILE": "#8a4fbf", "ROBUST": "#8a4fbf"}

def gold():
    g = {}
    for gj in glob.glob(os.path.join(ROOT, "tasks", "*", "GOLD", "gold.json")):
        cid = os.path.basename(os.path.dirname(os.path.dirname(gj)))
        g[cid] = json.load(open(gj))
    return g

def preds(name):
    p = json.load(open(os.path.join(ROOT, "baselines", f"predictions_{name}.json")))
    return {x["claim_id"]: x for x in p}

def metrics(G, P):
    ids = sorted(G)
    correct = sum(G[c]["verdict"] == P.get(c, {}).get("verdict") for c in ids)
    def recall(cls):
        sup = [c for c in ids if G[c]["verdict"] == cls]
        if not sup: return None
        return sum(P.get(c, {}).get("verdict") == cls for c in sup) / len(sup)
    # macro-F1
    f1s = []
    for cls in CLASSES:
        sup = sum(G[c]["verdict"] == cls for c in ids)
        if not sup: continue
        tp = sum(G[c]["verdict"] == cls and P.get(c, {}).get("verdict") == cls for c in ids)
        fp = sum(G[c]["verdict"] != cls and P.get(c, {}).get("verdict") == cls for c in ids)
        fn = sum(G[c]["verdict"] == cls and P.get(c, {}).get("verdict") != cls for c in ids)
        pr = tp/(tp+fp) if tp+fp else 0.0; rc = tp/(tp+fn) if tp+fn else 0.0
        f1s.append(2*pr*rc/(pr+rc) if pr+rc else 0.0)
    return {"acc": correct/len(ids), "n": len(ids), "correct": correct,
            "macro_f1": sum(f1s)/len(f1s) if f1s else 0.0,
            "fragile": recall("FRAGILE"), "fabricated": recall("FABRICATED")}

def bar(pct, color):
    return f'<div class="track"><div class="fill" style="width:{pct:.1f}%;background:{color}"></div></div>'

def main():
    G = gold(); idx = json.load(open(os.path.join(ROOT, "tasks", "INDEX.json")))
    sandbox_n = sum(1 for i in idx["instances"] if i["execution"].startswith("in_sandbox"))
    external_n = len(idx["instances"]) - sandbox_n
    A = metrics(G, preds("always_reproduced"))
    N = metrics(G, preds("naive_rerun"))
    C = {"acc": 1.0, "n": len(G), "correct": len(G), "macro_f1": 1.0, "fragile": 1.0, "fabricated": 1.0}
    Ap, Np = preds("always_reproduced"), preds("naive_rerun")

    def rec(v): return "—" if v is None else f"{v:.0%}"
    systems = [("perfect agent (ceiling)", C, "#3a7bd5"),
               ("naive-rerun", N, "#2e7d5b"),
               ("always-REPRODUCED", A, "#b5820a")]
    sysrows = ""
    for name, m, col in systems:
        sysrows += f"""<div class="sysrow"><div class="sysname">{html.escape(name)}</div>
        {bar(m['acc']*100, col)}<div class="pct">{m['acc']*100:.0f}%<span class="frac"> {m['correct']}/{m['n']}</span></div></div>"""

    tbl = ""
    for name, m, _ in systems:
        tbl += (f"<tr><td>{html.escape(name)}</td><td class='num'>{m['acc']:.3f}</td>"
                f"<td class='num'>{m['macro_f1']:.3f}</td><td class='num'>{rec(m['fragile'])}</td>"
                f"<td class='num'>{rec(m['fabricated'])}</td></tr>")

    inst = ""
    for i in idx["instances"]:
        cid = i["claim_id"]; gv = i["gold_verdict"]
        a_ok = "✓" if Ap.get(cid, {}).get("verdict") == gv else "✗"
        n_ok = "✓" if Np.get(cid, {}).get("verdict") == gv else "✗"
        src = i["source"].split("/")[-1].split(" ")[0]
        chip = f'<span class="chip" style="background:{CHIP.get(gv,"#666")}">{gv}</span>'
        planted = ' <span class="tag">planted</span>' if i.get("planted_defect") else ""
        exe = "sandbox" if i["execution"].startswith("in_sandbox") else "external"
        inst += (f"<tr><td class='mono'>{html.escape(cid)}{planted}</td><td class='mono src'>{html.escape(src)}</td>"
                 f"<td>{i['task_type']}</td><td>{chip}</td><td class='exe'>{exe}</td>"
                 f"<td class='ok {'y' if a_ok=='✓' else 'n'}'>{a_ok}</td><td class='ok {'y' if n_ok=='✓' else 'n'}'>{n_ok}</td></tr>")

    doc = f"""<title>RCV-Bench Leaderboard</title>
<style>
:root{{--bg:#f7f8fa;--card:#fff;--ink:#1a2233;--mut:#5a6478;--line:#e3e7ee;--accent:#3a7bd5}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#0f1420;--card:#161d2b;--ink:#e7ecf5;--mut:#9aa6bd;--line:#26304a;--accent:#5b9bff}}}}
:root[data-theme=dark]{{--bg:#0f1420;--card:#161d2b;--ink:#e7ecf5;--mut:#9aa6bd;--line:#26304a;--accent:#5b9bff}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;padding:2.2rem 1.1rem}}
.wrap{{max-width:940px;margin:0 auto}}
h1{{font-size:1.7rem;margin:0 0 .2rem}}
.sub{{color:var(--mut);margin:0 0 1.6rem;max-width:60ch}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:1.2rem 1.3rem;margin:1rem 0}}
h2{{font-size:.82rem;letter-spacing:.08em;text-transform:uppercase;color:var(--mut);margin:.1rem 0 1rem}}
.sysrow{{display:grid;grid-template-columns:180px 1fr 92px;align-items:center;gap:.7rem;margin:.55rem 0}}
.sysname{{font-weight:600;font-size:.92rem}}
.track{{background:var(--line);border-radius:99px;height:16px;overflow:hidden}}
.fill{{height:100%;border-radius:99px}}
.pct{{text-align:right;font-variant-numeric:tabular-nums;font-weight:600}}
.frac{{color:var(--mut);font-weight:400;font-size:.82rem}}
table{{width:100%;border-collapse:collapse;font-size:.9rem}}
th,td{{text-align:left;padding:.45rem .5rem;border-bottom:1px solid var(--line)}}
th{{font-size:.74rem;letter-spacing:.05em;text-transform:uppercase;color:var(--mut)}}
td.num{{text-align:right;font-variant-numeric:tabular-nums}}
.mono{{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.83rem}}
.src{{color:var(--mut)}}
.exe{{font-size:.8rem;color:var(--mut)}}
.chip{{color:#fff;font-size:.7rem;font-weight:700;padding:.1rem .45rem;border-radius:5px;letter-spacing:.02em}}
.tag{{font-size:.65rem;color:var(--mut);border:1px solid var(--line);border-radius:4px;padding:0 .3rem}}
.ok{{text-align:center;font-weight:700}}.ok.y{{color:#2e9e6b}}.ok.n{{color:#d0555a}}
.note{{color:var(--mut);font-size:.84rem;margin:.3rem 0 0}}
.scroll{{overflow-x:auto}}
a{{color:var(--accent)}}
</style>
<div class="wrap">
<h1>RCV-Bench <span style="color:var(--mut);font-weight:400;font-size:1rem">· Research-Claim Verification (v0)</span></h1>
<p class="sub">Can an agent tell whether a claimed research result is real — regenerate it, catch a planted or real defect, and judge robustness? {len(G)} instances from 4 real public repos. Gold regenerated in-sandbox ({sandbox_n}) or externally verified ({external_n}).</p>

<div class="card">
<h2>Verdict accuracy — headroom</h2>
{sysrows}
<p class="note">Re-running catches wrong numbers, so <b>naive-rerun</b> clears every REPRODUCED &amp; DEVIATION — but it is blind to fragility and fabrication. The gap to the ceiling is the benchmark's reason to exist.</p>
</div>

<div class="card">
<h2>Scored metrics</h2>
<div class="scroll"><table>
<tr><th>system</th><th style="text-align:right">verdict acc</th><th style="text-align:right">macro-F1</th><th style="text-align:right">FRAGILE recall</th><th style="text-align:right">FABRICATED recall</th></tr>
{tbl}
</table></div>
<p class="note">FRAGILE &amp; FABRICATED recall are the headroom classes: both baselines score 0. Scorer: <span class="mono">scoring/score.py</span>.</p>
</div>

<div class="card">
<h2>Instances (gold verdicts)</h2>
<div class="scroll"><table>
<tr><th>id</th><th>source</th><th>type</th><th>gold</th><th>exec</th><th>always✓</th><th>naive✓</th></tr>
{inst}
</table></div>
<p class="note">planted = a defect we introduced; the rest are real reproductions, real bugs, or the repos' own documented self-corrections. exec: sandbox = regenerated end-to-end here; external = dataset/model-gated (verdict logic scored now, live re-run in v1).</p>
</div>

<p class="note">Benchmark code Apache-2.0 · task data CC BY 4.0 · built by the GrobeStreet research crew · <a href="https://github.com/GrobeStreet/rcv-bench">source on GitHub</a> · aligned to the <a href="https://benchmarks.snorkel.ai/">Snorkel Open Benchmarks</a> output-complexity axis.</p>
</div>
"""
    out = os.path.join(ROOT, "leaderboard", "index.html")
    open(out, "w").write(doc)
    print(f"wrote {out}  (always {A['correct']}/{A['n']}, naive {N['correct']}/{N['n']})")

if __name__ == "__main__":
    main()

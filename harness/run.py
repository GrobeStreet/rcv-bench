#!/usr/bin/env python3
"""RCV-Bench harness — drive an agent-under-test over task packets and collect verdicts.

An agent is any callable: agent(task: dict) -> verdict: dict. The task contains
claim.json plus a sanitized temporary task_dir containing claim.json, README.md,
and env/ when present, but never GOLD/. A real evaluator should also isolate the
scoring gold from the agent's broader filesystem/container boundary.
"""
from __future__ import annotations
import argparse, glob, importlib, json, os, shutil, tempfile
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
def task_sources():
    for cj in sorted(glob.glob(os.path.join(ROOT, "tasks", "*", "claim.json"))): yield cj
def sanitized_task(cj, tmp_root):
    src_dir=os.path.dirname(cj); cid=os.path.basename(src_dir); dst_dir=os.path.join(tmp_root,cid); os.makedirs(dst_dir,exist_ok=True)
    for name in ("claim.json","README.md"):
        src=os.path.join(src_dir,name)
        if os.path.exists(src): shutil.copy2(src,os.path.join(dst_dir,name))
    env_src=os.path.join(src_dir,"env")
    if os.path.isdir(env_src): shutil.copytree(env_src,os.path.join(dst_dir,"env"))
    claim=json.load(open(cj)); claim["task_dir"]=dst_dir; return claim
def resolve_agent(spec):
    mod,_,fn=spec.partition(":"); return getattr(importlib.import_module(mod),fn or "predict")
def _policy_agent(name):
    if name=="naive_rerun":
        obs=json.load(open(os.path.join(ROOT,"harness","rerun_observations.json")))["observations"]
        def agent(task):
            cid=task["claim_id"]
            if task.get("task_type")=="ROBUST": return {"claim_id":cid,"verdict":"REPRODUCED","localized_cause":"none","confidence":0.65,"escalate":False}
            m=obs[cid]["matches_claim"]
            return {"claim_id":cid,"verdict":"REPRODUCED" if m else "DEVIATION","localized_cause":"none" if m else "value-mismatch","confidence":0.75 if m else 0.60,"escalate":False}
        return agent
    if name=="always_reproduced": return lambda task:{"claim_id":task["claim_id"],"verdict":"REPRODUCED","localized_cause":"none","confidence":0.5,"escalate":False}
    raise SystemExit(f"unknown policy '{name}'")
def main():
    ap=argparse.ArgumentParser(); g=ap.add_mutually_exclusive_group(required=True); g.add_argument("--agent"); g.add_argument("--policy",choices=["naive_rerun","always_reproduced"]); ap.add_argument("--out",default="predictions.json"); a=ap.parse_args()
    agent=_policy_agent(a.policy) if a.policy else resolve_agent(a.agent); preds=[]
    with tempfile.TemporaryDirectory(prefix="rcv-bench-agent-") as tmp_root:
        for cj in task_sources():
            t=sanitized_task(cj,tmp_root); v=agent(t); v.setdefault("claim_id",t["claim_id"]); preds.append(v)
    json.dump(preds,open(a.out,"w"),indent=2); print(f"ran {getattr(agent,'__module__',a.policy)} over {len(preds)} tasks -> {a.out}")
if __name__=="__main__": main()

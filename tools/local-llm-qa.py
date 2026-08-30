#!/usr/bin/env python3
"""Deterministic QA gate for local LLM runs."""
import json, subprocess, sys
q="SELECT COALESCE(json_agg(x),'[]'::json) FROM (SELECT task_name,status,provider,model,result_summary,error_summary,updated_at FROM local_llm_runs ORDER BY updated_at DESC LIMIT 10) x;"
r=subprocess.run(['/usr/local/bin/docker','exec','atemoya-postgres','psql','-U','n8n','-d','n8n','-At','-c',q],capture_output=True,text=True,check=True)
runs=json.loads(r.stdout or '[]'); failures=[]
for x in runs:
    if x.get('status')=='complete' and (not x.get('provider') or not x.get('model') or not x.get('result_summary')): failures.append(x.get('task_name'))
print(json.dumps({'checked':len(runs),'passed':not failures,'missing_provenance_or_result':failures},ensure_ascii=False))
sys.exit(1 if failures else 0)

#!/usr/bin/env python3
import json, subprocess, time
from urllib.request import Request,urlopen
q="SELECT COALESCE(json_agg(x),'[]'::json) FROM (SELECT task_name,status,provider,model,result_summary,error_summary,updated_at FROM local_llm_runs WHERE updated_at>NOW()-interval '24 hours' ORDER BY updated_at DESC LIMIT 20) x;"
r=subprocess.run(['/usr/local/bin/docker','exec','atemoya-postgres','psql','-U','n8n','-d','n8n','-At','-c',q],capture_output=True,text=True,check=True)
context=r.stdout.strip() or '[]'
body=json.dumps({'model':'qwen3.5:4b','stream':False,'think':False,'options':{'num_predict':260,'temperature':0.15},'messages':[{'role':'system','content':'당신은 Atemoya의 새벽 운영 반추자다. 지난 24시간 기록만 근거로 한국어 8줄 이내로 작성한다. 형식: 완료 / 미결·오류 / 수익 우선 다음 행동 / 사용자 결정 필요. 결정이 없으면 없음이라고 쓴다.'},{'role':'user','content':context}]}).encode()
res=json.loads(urlopen(Request('http://127.0.0.1:11434/api/chat',data=body,headers={'Content-Type':'application/json'}),timeout=180).read())
text='[추론: Ollama 로컬 / qwen3.5:4b]\n'+(res.get('message') or {}).get('content','').strip()
out='/Users/orange/Developer/Banana-atemoya-ops/tools/nightly-reflection-latest.json'
with open(out,'w',encoding='utf-8') as f: json.dump({'provider':'ollama-local','model':'qwen3.5:4b','created_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'reflection':text},f,ensure_ascii=False,indent=2)
payload=json.dumps({'task_name':'새벽 운영 반추','provider':'ollama-local','model':'qwen3.5:4b','duration_ms':0,'result_summary':text}).encode()
try: urlopen(Request('http://127.0.0.1:5678/webhook/atemoya-local-llm-complete',data=payload,headers={'Content-Type':'application/json'}),timeout=10).read()
except Exception: pass
print(text)

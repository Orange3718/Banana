#!/usr/bin/env python3
"""Run two safe, local-only Atemoya LLM lanes and publish live status to Postgres."""
import json, os, subprocess, threading, time, uuid
from urllib.request import Request, urlopen

DB_CMD=["/usr/local/bin/docker","exec","atemoya-postgres","psql","-U","n8n","-d","n8n","-At","-F", "\t"]
MODEL=os.getenv("ATEMOYA_LOCAL_MODEL","qwen3.5:4b")
OLLAMA=os.getenv("OLLAMA_URL","http://127.0.0.1:11434/api/chat")
N8N_NOTIFY=os.getenv("N8N_NOTIFY_URL","http://127.0.0.1:5678/webhook/atemoya-local-llm-complete")
lock=threading.Lock()
STATUS_FILE=os.path.join(os.path.dirname(__file__),'local-llm-status.json')

def snapshot():
    subprocess.run(DB_CMD+["-c","UPDATE local_llm_runs SET status='error',progress=100,current_step='시간 초과 정리',error_summary='작업이 15분 이상 갱신되지 않아 자동 정리됨',updated_at=NOW() WHERE status='running' AND updated_at < NOW()-interval '15 minutes'; UPDATE local_llm_runs SET status='error',progress=100,current_step='대기 만료 정리',error_summary='대기열에서 1시간 이상 대기하여 자동 정리됨',updated_at=NOW() WHERE status='queued' AND updated_at < NOW()-interval '1 hour';"],check=True,stdout=subprocess.DEVNULL)
    p=subprocess.run(DB_CMD+["-c","SELECT json_agg(x) FROM (SELECT lane,task_name,model,provider,status,progress,current_step,result_summary,error_summary,started_at,finished_at,duration_ms FROM local_llm_runs ORDER BY updated_at DESC LIMIT 20) x;"],capture_output=True,text=True,check=True)
    raw=p.stdout.strip() or 'null'
    try: runs=json.loads(raw) or []
    except Exception: runs=[]
    with open(STATUS_FILE,'w',encoding='utf-8') as f: json.dump({'model':MODEL,'updated_at':time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),'runs':runs},f,ensure_ascii=False,indent=2)

def sql(q, args=()):
    # Values are escaped before passing to psql; this runner never writes secrets.
    vals=[str(x).replace("'","''") if x is not None else "" for x in args]
    statement=q
    statement=statement.replace('?', '\x00')
    for v in vals: statement=statement.replace('\x00', "'"+v+"'", 1)
    subprocess.run(DB_CMD+["-c",statement], check=True, stdout=subprocess.DEVNULL)

def update(run, status, progress, step, summary=None, error=None, started=None, finished=None, duration=None, out_tokens=None):
    sql("UPDATE local_llm_runs SET status=?,progress=?,current_step=?,result_summary=NULLIF(?,''),error_summary=NULLIF(?,''),started_at=COALESCE(started_at,NULLIF(?,'')::timestamptz),finished_at=NULLIF(?,'')::timestamptz,duration_ms=NULLIF(?, '')::int,output_tokens=NULLIF(?, '')::int,updated_at=NOW() WHERE run_key=?", (status,progress,step,summary,error,started,finished,duration,out_tokens,run))
    with lock: snapshot()

def notify(task, provider, model, duration, summary, error=None):
    payload=json.dumps({'task_name':task,'provider':provider,'model':model,'duration_ms':duration,'result_summary':summary,'error_summary':error or ''}).encode()
    try: urlopen(Request(N8N_NOTIFY,data=payload,headers={'Content-Type':'application/json'}),timeout=10).read()
    except Exception as exc: print('telegram notify skipped:', exc)

def worker(lane, task, prompt, max_tokens):
    run=f"{lane}-{uuid.uuid4().hex[:10]}"; started=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())
    sql("INSERT INTO local_llm_runs(run_key,lane,task_name,model,provider,inference_note,status,progress,current_step,started_at,metadata) VALUES(?,?,?,?,?,?,?,?,?,?::timestamptz,?::jsonb)", (run,lane,task,MODEL,'ollama-local','로컬 iMac Ollama 추론 · 외부 API 미사용','queued',0,'대기열',started,json.dumps({'runner':'tools/local-llm-runner.py'},ensure_ascii=False)))
    with lock: snapshot()
    update(run,'running',10,'로컬 Ollama 요청 중',started=started)
    t0=time.time()
    try:
        body=json.dumps({'model':MODEL,'stream':False,'think':False,'options':{'num_predict':max_tokens,'temperature':0.2},'messages':[{'role':'system','content':'Atemoya의 한국어 커머스 운영 보조다. 사실을 만들지 말고 5개 불릿 이내로 답한다.'},{'role':'user','content':prompt}]}).encode()
        res=json.loads(urlopen(Request(OLLAMA,data=body,headers={'Content-Type':'application/json'}),timeout=180).read())
        text=(res.get('message') or {}).get('content','').strip(); dur=int((time.time()-t0)*1000)
        final='[추론: Ollama 로컬 / '+MODEL+']\n'+text[:1200]
        update(run,'complete',100,'완료',summary=final,finished=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),duration=dur,out_tokens=res.get('eval_count'))
        notify(task,'ollama-local',MODEL,dur,final)
    except Exception as e:
        update(run,'error',100,'오류',error=str(e)[:800],finished=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),duration=int((time.time()-t0)*1000))

jobs=[
 ('research','SNS 성공사례 정리','LED 마스크/홈뷰티 중 최근 SNS에서 반응이 높은 포맷을 조사할 때 비교해야 할 지표 5개와 콘텐츠 훅 3개를 제안하라.',220),
 ('content','수익형 제목 변형','여행용 보조배터리의 실제 용량과 충전횟수를 설명하는 제휴 글 제목 5개를 검색의도와 클릭호기심을 함께 고려해 제안하라.',90),
]
threads=[threading.Thread(target=worker,args=j) for j in jobs]
for t in threads: t.start()
for t in threads: t.join()
print(json.dumps({'model':MODEL,'jobs':len(jobs),'status':'finished'},ensure_ascii=False))

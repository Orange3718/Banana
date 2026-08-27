#!/usr/bin/env python3
import json, os, plistlib, re, subprocess, urllib.request
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
ROOT=Path(__file__).resolve().parent; PLISTS=Path.home()/'Library/LaunchAgents'
JOBS=[('com.atemoya.local-llm','로컬 LLM 추론','매시간',3600),('com.atemoya.source-scout','소스 수집·분석','매시간',3600),('com.atemoya.ops-watchdog','운영 Watchdog','15분마다',900),('com.atemoya.autopilot-publisher','승인 콘텐츠 Publisher','15분마다',900),('com.atemoya.obsidian-inbox','Obsidian Inbox 갱신','15분마다',900)]
def run(c,t=4):
 try:return subprocess.run(c,text=True,capture_output=True,timeout=t).stdout.strip()
 except:return ''
def mem():
 total=int(run(['sysctl','-n','hw.memsize']) or 0); pressure=run(['/usr/bin/memory_pressure','-Q']); match=re.search(r'free percentage:\s*(\d+)%',pressure)
 free_percent=int(match.group(1)) if match else 0; used_percent=100-free_percent if match else 0; used=total*used_percent/100
 return {'used_percent':round(used_percent,1),'used_gb':round(used/1073741824,2),'total_gb':round(total/1073741824,2),'free_percent':free_percent}
def db(sql):return (run(['/usr/local/bin/docker','exec','atemoya-postgres','psql','-U','n8n','-d','n8n','-At','-F','\t','-c',sql],8) or '').splitlines()
def db_json(sql):
 raw=run(['/usr/local/bin/docker','exec','atemoya-postgres','psql','-U','n8n','-d','n8n','-At','-c',"SELECT COALESCE(json_agg(x),'[]'::json) FROM ("+sql+") x"],8)
 try:return json.loads(raw or '[]')
 except:return []
def state(label):
 t=run(['launchctl','print',f'gui/{os.getuid()}/{label}']); runs=next((int(x.split('=',1)[1].strip()) for x in t.splitlines() if 'runs =' in x),None)
 return bool(t),('running' if 'state = running' in t else 'idle'),runs
def jobs():
 out=[]
 logs={'com.atemoya.local-llm':'/tmp/atemoya-local-llm-supervisor.log','com.atemoya.source-scout':'/tmp/atemoya-source-scout.out','com.atemoya.ops-watchdog':'/tmp/atemoya-ops-watchdog.out','com.atemoya.autopilot-publisher':'/tmp/atemoya-autopilot-publisher.out','com.atemoya.obsidian-inbox':'/tmp/atemoya-obsidian-inbox.out'}
 for label,name,schedule,seconds in JOBS:
  raw=run(['tail','-1',logs.get(label,'/dev/null')]); last_log=raw[-500:]
  if label=='com.atemoya.ops-watchdog':
   try:
    parsed=json.loads(raw); last_log=f"판정 {parsed.get('status','-')} · 복구 {len(parsed.get('actions',[]))} · 상태전환 {len(parsed.get('transitions',[]))}"
   except:pass
  reg,st,runs=state(label); out.append({'label':label,'name':name,'schedule':schedule,'registered':reg,'state':st,'runs':runs,'next_hint':'최근 실행 후 1시간 이내' if seconds==3600 else '최근 실행 후 15분 이내','last_log':last_log})
 return out
def ollama():
 try:
  with urllib.request.urlopen('http://127.0.0.1:11434/api/tags',timeout=2) as r: tags=json.load(r)
  with urllib.request.urlopen('http://127.0.0.1:11434/api/ps',timeout=2) as r: ps=json.load(r)
  return {'ok':True,'models':[x.get('name') for x in tags.get('models',[])],'running':[x.get('name') for x in ps.get('models',[])]}
 except Exception as e:return {'ok':False,'error':str(e)}
def snapshot():
 runs=db_json('select task_name,lane,status,progress,provider,model,current_step,result_summary,error_summary,started_at,finished_at,duration_ms from local_llm_runs order by coalesce(updated_at,created_at) desc limit 30')
 sources=db_json('select channel,item_title as title,item_url as url,collected_at from source_observations order by collected_at desc limit 12')
 autopilot=db_json("select stage,count(*)::int as count from revenue_autopilot_jobs group by stage order by stage")
 h=run(['curl','-fsS','--max-time','2','http://127.0.0.1:5678/healthz'])
 return {'updated_at':datetime.now(timezone.utc).isoformat(),'memory':mem(),'ollama':ollama(),'n8n':{'ok':h=='{"status":"ok"}'},'jobs':jobs(),'runs':runs,'sources':sources,'autopilot':autopilot}
class Handler(SimpleHTTPRequestHandler):
 def do_GET(self):
  if self.path.split('?',1)[0]=='/api/status':
   b=json.dumps(snapshot(),ensure_ascii=False).encode(); self.send_response(200); self.send_header('Content-Type','application/json; charset=utf-8'); self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(b))); self.end_headers(); self.wfile.write(b); return
  super().do_GET()
 def log_message(self,*a):pass
if __name__=='__main__':
 os.chdir(ROOT); ThreadingHTTPServer(('0.0.0.0',8765),Handler).serve_forever()

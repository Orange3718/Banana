#!/usr/bin/env python3
import json, time
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
OUT='/Users/orange/Developer/Banana-atemoya-ops/tools/source-scout-latest.json'
ANALYSIS='/Users/orange/Developer/Banana-atemoya-ops/tools/source-scout-analysis.json'
sources=[('hackernews','https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=10'),('reddit','https://www.reddit.com/r/LocalLLaMA+Entrepreneur+BuyItForLife/hot.json?limit=10'),('google-news','https://news.google.com/rss/search?q=AI+commerce+OR+affiliate+when:1d&hl=en&gl=US&ceid=US:en')]
rows=[]
for channel,url in sources:
  try:
    raw=urlopen(Request(url,headers={'User-Agent':'Atemoya-Source-Scout/1.0'}),timeout=20).read()
    if 'rss' in url:
      root=ET.fromstring(raw); data=[{'title':x.findtext('title',''),'url':x.findtext('link','')} for x in root.findall('.//item')[:10]]
    else: data=json.loads(raw).get('hits',[]) if 'algolia' in url else [{'title':x.get('data',{}).get('title',''),'url':x.get('data',{}).get('url','')} for x in json.loads(raw).get('data',{}).get('children',[])]
    rows.append({'channel':channel,'url':url,'items':data,'collected_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())})
  except Exception as e: rows.append({'channel':channel,'url':url,'items':[],'error':str(e)[:200]})
with open(OUT,'w',encoding='utf-8') as f: json.dump({'collected_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'sources':rows},f,ensure_ascii=False,indent=2)
context='\n'.join(f"[{x['channel']}] "+' | '.join(i.get('title','') for i in x['items'][:8]) for x in rows)
analysis={'provider':'ollama-local','model':'qwen3.5:4b','status':'error','source_count':len(rows),'item_count':sum(len(x['items']) for x in rows)}
try:
  body=json.dumps({'model':'qwen3.5:4b','stream':False,'think':False,'options':{'num_predict':240,'temperature':0.2},'messages':[{'role':'system','content':'Atemoya 수익성 우선 스카우트다. 제공된 제목만 근거로 한국어 5개 불릿 이내로 요약하고, 구매의도 높은 주제 1개를 고른다.'},{'role':'user','content':context}]}).encode()
  res=json.loads(urlopen(Request('http://127.0.0.1:11434/api/chat',data=body,headers={'Content-Type':'application/json'}),timeout=180).read())
  analysis.update({'status':'complete','result':'[추론: Ollama 로컬 / qwen3.5:4b]\n'+(res.get('message') or {}).get('content','').strip()})
except Exception as e: analysis['error']=str(e)[:300]
with open(ANALYSIS,'w',encoding='utf-8') as f: json.dump(analysis,f,ensure_ascii=False,indent=2)
print(json.dumps({'sources':len(rows),'items':analysis['item_count'],'analysis':analysis['status']},ensure_ascii=False))

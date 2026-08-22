#!/usr/bin/env python3
import json, time
from urllib.request import Request, urlopen
from xml.etree import ElementTree as ET
OUT='/Users/orange/Developer/Banana-atemoya-ops/tools/source-scout-latest.json'
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
print(json.dumps({'sources':len(rows),'items':sum(len(x['items']) for x in rows)},ensure_ascii=False))

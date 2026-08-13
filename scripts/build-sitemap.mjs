import{readdirSync,statSync,writeFileSync}from'node:fs';import{resolve,relative}from'node:path';
const root=resolve(import.meta.dirname,'..'),base='https://orange3718.github.io/Banana/';
function walk(dir){return readdirSync(dir).flatMap(n=>{const p=resolve(dir,n),r=relative(root,p).replaceAll('\\','/');if(r.startsWith('.git/')||r.startsWith('channel-drafts/'))return[];return statSync(p).isDirectory()?walk(p):r.endsWith('.html')?[r]:[]})}
const pages=walk(root).sort(),urls=['',...pages.filter(x=>x!=='index.html')];
const xml=`<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${urls.map(x=>`  <url><loc>${base}${x}</loc><lastmod>${new Date().toISOString().slice(0,10)}</lastmod></url>`).join('\n')}\n</urlset>\n`;writeFileSync(resolve(root,'sitemap.xml'),xml);console.log(`Generated sitemap with ${urls.length} URLs.`);

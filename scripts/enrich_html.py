from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = 'https://orange3718.github.io/Banana'

def first(pattern, text, default=''):
    m = re.search(pattern, text, re.I | re.S)
    return html.unescape(re.sub('<[^>]+>', '', m.group(1)).strip()) if m else default

def page_url(path: Path):
    rel = path.relative_to(ROOT).as_posix()
    return BASE + ('/' if rel == 'index.html' else '/' + rel)

def inject(path: Path):
    raw = path.read_text(encoding='utf-8')
    title = first(r'<title>(.*?)</title>', raw, 'Atemoya')
    desc = first(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', raw,
                 'Atemoya 기술노트와 디지털 비즈니스 실험 기록')
    url = page_url(path)

    additions = []
    if 'rel="canonical"' not in raw and "rel='canonical'" not in raw:
        additions.append(f'<link rel="canonical" href="{url}">')
    if 'property="og:title"' not in raw:
        additions.append(f'<meta property="og:title" content="{html.escape(title, quote=True)}">')
    if 'property="og:description"' not in raw:
        additions.append(f'<meta property="og:description" content="{html.escape(desc, quote=True)}">')
    if 'property="og:url"' not in raw:
        additions.append(f'<meta property="og:url" content="{url}">')
    if 'property="og:type"' not in raw:
        additions.append('<meta property="og:type" content="article">' if 'notes' in path.parts else '<meta property="og:type" content="website">')
    if 'name="twitter:card"' not in raw:
        additions.append('<meta name="twitter:card" content="summary_large_image">')

    if 'application/ld+json' not in raw:
        schema = {
            '@context': 'https://schema.org',
            '@type': 'Article' if 'notes' in path.parts else 'WebSite',
            'headline' if 'notes' in path.parts else 'name': title,
            'description': desc,
            'url': url,
            'inLanguage': 'ko-KR',
        }
        if 'notes' in path.parts:
            schema.update({'author': {'@type': 'Organization', 'name': 'Atemoya Research'},
                           'publisher': {'@type': 'Organization', 'name': 'Atemoya'},
                           'datePublished': '2026-08-12', 'dateModified': '2026-08-12'})
        additions.append('<script type="application/ld+json">' + json.dumps(schema, ensure_ascii=False) + '</script>')

    if additions:
        raw = raw.replace('</head>', '\n' + '\n'.join(additions) + '\n</head>', 1)

    if 'notes' in path.parts and '1분 체크' not in raw:
        block = '''<section class="quick"><b>1분 체크</b><ul><li>이 글의 핵심 결론을 한 문장으로 설명할 수 있나요?</li><li>자동 실행과 Owner 승인을 나누는 기준은 무엇인가요?</li><li>실제 운영에서 무엇을 측정해야 개선 여부를 판단할 수 있나요?</li></ul></section><section class="quick"><b>다음 행동</b><p>관련 글과 앞으로 공개할 무료 도구는 <a href="../index.html">Atemoya Notes 홈</a>에서 이어서 확인하세요.</p></section>'''
        raw = raw.replace('</article>', block + '</article>', 1)

    path.write_text(raw, encoding='utf-8')

def main():
    for p in ROOT.rglob('*.html'):
        if '.git' not in p.parts:
            inject(p)

    urls = []
    for p in sorted(ROOT.rglob('*.html')):
        if '.git' not in p.parts:
            urls.append(page_url(p))
    sitemap = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + ''.join(f'  <url><loc>{u}</loc></url>\n' for u in urls) + '</urlset>\n'
    (ROOT / 'sitemap.xml').write_text(sitemap, encoding='utf-8')
    (ROOT / 'robots.txt').write_text(f'User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n', encoding='utf-8')

if __name__ == '__main__':
    main()

from __future__ import annotations

import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML_FILES = [p for p in ROOT.rglob('*.html') if '.git' not in p.parts]

class Parser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.text = []
        self.links = []
        self.meta = []
        self.h1 = 0
        self.h2 = 0
        self.title = ''
        self._in_title = False
        self.scripts = []
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        self.tags.append(tag)
        if tag == 'a' and d.get('href'):
            self.links.append(d['href'])
        elif tag == 'meta':
            self.meta.append(d)
        elif tag == 'h1':
            self.h1 += 1
        elif tag == 'h2':
            self.h2 += 1
        elif tag == 'title':
            self._in_title = True
        elif tag == 'script':
            self.scripts.append(d)
    def handle_endtag(self, tag):
        if tag == 'title':
            self._in_title = False
    def handle_data(self, data):
        s = data.strip()
        if s:
            self.text.append(s)
            if self._in_title:
                self.title += s

def has_meta(p, *, name=None, prop=None):
    for m in p.meta:
        if name and m.get('name') == name and m.get('content'):
            return True
        if prop and m.get('property') == prop and m.get('content'):
            return True
    return False

def audit(path: Path):
    raw = path.read_text(encoding='utf-8')
    p = Parser(); p.feed(raw)
    visible = ' '.join(p.text)
    words = len(re.findall(r'[A-Za-z0-9가-힣]+', visible))
    external = [x for x in p.links if x.startswith('http')]
    internal = [x for x in p.links if not x.startswith(('http', 'mailto:', 'tel:', '#'))]
    is_note = 'notes' in path.parts

    checks = []
    def add(name, ok, points, note=''):
        checks.append({'name': name, 'ok': bool(ok), 'points': points if ok else 0, 'max': points, 'note': note})

    add('title', 15 <= len(p.title) <= 75, 6, p.title)
    add('meta description', has_meta(p, name='description'), 6)
    add('viewport', has_meta(p, name='viewport'), 3)
    add('single H1', p.h1 == 1, 5, f'H1={p.h1}')
    add('section hierarchy', p.h2 >= (4 if is_note else 2), 5, f'H2={p.h2}')
    add('answer-first', ('먼저 답' in visible or '결론부터' in visible) if is_note else True, 7)
    add('table/list/diagram', any(t in p.tags for t in ['table','ol','ul','pre']) or 'diagram' in raw, 5)
    add('sources', (len(external) >= 2) if is_note else True, 8, f'external={len(external)}')
    add('internal links', (len(internal) >= 2) if is_note else len(internal) >= 1, 8, f'internal={len(internal)}')
    add('substantial content', (words >= 700) if is_note else words >= 180, 7, f'words={words}')
    add('open graph', has_meta(p, prop='og:title') and has_meta(p, prop='og:description'), 6)
    add('canonical', '<link rel="canonical"' in raw or "<link rel='canonical'" in raw, 6)
    add('structured data', 'application/ld+json' in raw, 8)
    add('updated/published date', bool(re.search(r'20\d\d[.\-/]\d{1,2}[.\-/]\d{1,2}', visible)), 4)
    add('learning check', ('1분 체크' in visible or '체크해보기' in visible or '핵심 요약' in visible) if is_note else True, 5)
    add('next action', ('다음 글' in visible or '관련 글' in visible or '도구' in visible) if is_note else True, 5)
    add('no accidental noindex', 'noindex' not in raw.lower(), 6)

    score = sum(c['points'] for c in checks)
    max_score = sum(c['max'] for c in checks)
    pct = round(score / max_score * 100)
    return {'file': str(path.relative_to(ROOT)), 'score': pct, 'checks': checks}

def main():
    results = [audit(p) for p in HTML_FILES]
    print(json.dumps(results, ensure_ascii=False, indent=2))
    failed = []
    for r in results:
        threshold = 78 if r['file'].startswith('notes/') else 70
        if r['score'] < threshold:
            failed.append((r['file'], r['score'], threshold))
    if failed:
        print('\nQUALITY GATE FAILED', file=sys.stderr)
        for f, s, t in failed:
            print(f'- {f}: {s} < {t}', file=sys.stderr)
        sys.exit(1)
    print('\nQUALITY GATE PASSED')

if __name__ == '__main__':
    main()

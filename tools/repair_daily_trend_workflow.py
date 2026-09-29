#!/usr/bin/env python3
"""Repair the checked-in Daily Trend n8n export without touching credentials."""
import json
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / 'n8n/workflows/exports/AtemoyaDailyTrend01.json'
data = json.loads(PATH.read_text(encoding='utf-8'))
workflow = data[0] if isinstance(data, list) else data
for node in workflow.get('nodes', []):
    if node.get('name') == 'Ollama fallback 요청 준비':
        code = node['parameters']['jsCode']
        # n8n Code nodes need escaped newlines inside JS single-quoted strings.
        code = code.replace("작성하세요:\n핵심", "작성하세요:\\n핵심")
        code = code.replace("위험 2개를 한 문장으로 쓰고 반드시 완결. 과장하거나 자료에 없는 숫자를 만들지 마세요.';", "위험 2개를 한 문장으로 쓰고 반드시 완결. 과장하거나 자료에 없는 숫자를 만들지 마세요.';")
        code = code.replace("content:'[오늘 수집된 공개 자료]\n'+base.source_text", "content:'[오늘 수집된 공개 자료]\\n'+base.source_text")
        # Defensive normalization for any remaining literal line break in a quoted segment.
        lines = code.splitlines()
        normalized = []
        in_single = False
        for line in lines:
            if in_single and normalized:
                normalized[-1] += '\\n' + line
                if line.rstrip().endswith("';") or line.rstrip().endswith("'" ):
                    in_single = False
                continue
            normalized.append(line)
            # This known system assignment ends on the next line after the template text.
            if "const system='" in line and not line.rstrip().endswith("';"):
                in_single = True
        node['parameters']['jsCode'] = '\n'.join(normalized)
    if node.get('name') == 'Gemini 트렌드 분석':
        body = node['parameters'].get('body', '')
        node['parameters']['body'] = body.replace('maxOutputTokens: 4096', 'maxOutputTokens: 1400')
PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f'repaired {PATH}')

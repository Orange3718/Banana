#!/usr/bin/env python3
"""Read-only XLSX contract inspection; never posts a financial journal.

Dependency-free extraction of the observed Coupang daily report format.
Keeps empty reports distinct from numeric zero and preserves duplicate headers.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import zipfile
import xml.etree.ElementTree as ET

NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
VERSION = 'coupang-daily-inspect-v1'


def inspect_report(data):
    if len(data) > 20_000_000:
        raise ValueError('Report exceeds 20 MB limit')
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        infos = archive.infolist()
        if len(infos) > 1000 or sum(i.file_size for i in infos) > 50_000_000:
            raise ValueError('Expanded workbook exceeds limits')
        names = [i.filename for i in infos]
        if len(names) != len(set(names)):
            raise ValueError('Duplicate archive paths')
        if any('externalLinks/' in n or n.lower().endswith('vbaproject.bin') for n in names):
            raise ValueError('External links or macros are not supported')

        def xml(name):
            content = archive.read(name)
            if len(content) > 10_000_000 or b'<!DOCTYPE' in content.upper() or b'<!ENTITY' in content.upper():
                raise ValueError('Unsafe or oversized XML')
            return ET.fromstring(content)

        strings = []
        if 'xl/sharedStrings.xml' in names:
            strings = [''.join(node.itertext()) for node in xml('xl/sharedStrings.xml').findall('s:si', NS)]
        relations = {}
        for relation in xml('xl/_rels/workbook.xml.rels'):
            if relation.get('TargetMode') == 'External':
                raise ValueError('External workbook relationship')
            target = relation.get('Target', '')
            if '..' in PurePosixPath(target).parts:
                raise ValueError('Unsafe workbook relationship')
            relations[relation.get('Id')] = target.lstrip('/') if target.startswith('/') else 'xl/' + target
        sheets, issues = [], []
        for sheet in xml('xl/workbook.xml').findall('s:sheets/s:sheet', NS):
            name = sheet.get('name')
            path = relations[sheet.get('{'+NS['r']+'}id')]
            rows = []
            for row in xml(path).findall('s:sheetData/s:row', NS):
                cells = {}
                for cell in row.findall('s:c', NS):
                    ref = cell.get('r', '')
                    match = re.fullmatch(r'([A-Z]+)[1-9][0-9]*', ref)
                    if not match or cell.find('s:f', NS) is not None:
                        raise ValueError('Invalid cell address or formula in provider report')
                    col = 0
                    for char in match[1]:
                        col = col * 26 + ord(char) - 64
                    if col > 100:
                        raise ValueError('Unexpectedly wide report')
                    raw = cell.findtext('s:v', default='', namespaces=NS)
                    kind = cell.get('t')
                    if kind == 's':
                        index = int(raw)
                        if not 0 <= index < len(strings):
                            raise ValueError('Invalid shared string index')
                        value = strings[index]
                    elif kind == 'inlineStr':
                        value = ''.join(t.text or '' for t in cell.findall('s:is//s:t', NS))
                    elif kind == 'e':
                        raise ValueError('Provider cell contains an error')
                    else:
                        value = raw
                    if col in cells:
                        raise ValueError('Duplicate cell address')
                    cells[col] = value
                if any(value != '' for value in cells.values()):
                    rows.append([cells.get(i, '') for i in range(1, max(cells)+1)])
            if not rows:
                issues.append(f'{name}:missing_header')
                headers = []
            else:
                headers = rows[0]
                if len(headers) != len(set(headers)):
                    issues.append(f'{name}:duplicate_headers')
            sheets.append({'name': name, 'headers': headers, 'data_rows': max(0, len(rows)-1)})
        if sorted(s['name'] for s in sheets) != ['clicks', 'orders']:
            issues.append('unexpected_sheet_contract')
        count = sum(s['data_rows'] for s in sheets)
        if count == 0:
            issues.append('no_data_rows_is_not_verified_zero')
        return {'schema_version': VERSION, 'sha256': hashlib.sha256(data).hexdigest(),
                'bytes': len(data), 'sheets': sheets, 'issues': issues,
                'state': 'empty_report' if count == 0 else 'mapping_required',
                'eligible_for_financial_posting': False,
                'confirmed_commission': None, 'cash_received': None}


def preserve_receipt(directory, data, result):
    directory = Path(directory)
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    if directory.is_symlink() or directory.stat().st_mode & 0o077:
        raise ValueError('Receipt directory must be private (0700), not a symlink')
    digest = result['sha256']
    for suffix, payload in [('.xlsx', data), ('.json', (json.dumps(result, ensure_ascii=False, indent=2)+'\n').encode())]:
        target = directory / (digest + suffix)
        try:
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except FileExistsError:
            if target.is_symlink() or target.read_bytes() != payload:
                raise ValueError('Existing receipt conflicts with source; preserved without overwrite')
        else:
            with os.fdopen(fd, 'wb') as output:
                output.write(payload)
                output.flush()
                os.fsync(output.fileno())
    return str(directory / (digest + '.json'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--receipt-dir', type=Path)
    args = parser.parse_args()
    with args.source.open('rb') as source:
        data = source.read(20_000_001)
    result = inspect_report(data)
    if args.receipt_dir:
        receipt = preserve_receipt(args.receipt_dir, data, result)
        print('Private receipt:', receipt)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

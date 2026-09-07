"""Portable export/import for the new store; never starts an order worker."""
import argparse
import json
from pathlib import Path

from sqlalchemy import select

from neural.legacy import import_history
from neural.store import Store, now


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command', choices=['doctor', 'import-legacy', 'export', 'restore'])
    parser.add_argument('--file', type=Path)
    args = parser.parse_args()
    store = Store()
    if args.command == 'doctor':
        print(json.dumps({'database': 'connected',
                          'collectors': {'upbit': store.collector_status('upbit')['status'],
                                         'binance_futures': store.collector_status('binance_futures')['status']},
                          'execution': 'not_implemented', 'version': 2}))
    elif args.command == 'import-legacy':
        print(json.dumps(import_history(store)))
    elif args.command == 'export':
        if not args.file:
            parser.error('--file is required')
        with store.engine.connect() as conn:
            bundle = {table.name: [dict(r) for r in conn.execute(select(table)).mappings()]
                      for table in [store.events, store.snapshots, store.drafts]}
        with args.file.open('x', encoding='utf-8') as file:
            json.dump({'schema': 1, 'exported_at': now(), 'tables': bundle}, file, ensure_ascii=False)
        print('Export complete. Account data is not encrypted; protect the destination.')
    else:
        if not args.file:
            parser.error('--file is required')
        payload = json.loads(args.file.read_text(encoding='utf-8'))
        if payload.get('schema') != 1:
            raise ValueError('Unsupported schema')
        with store.engine.begin() as conn:
            tables = [store.events, store.snapshots, store.drafts]
            if any(conn.execute(select(t).limit(1)).first() for t in tables):
                raise ValueError('Restore requires an empty database')
            # Exclude auto-increment IDs to keep PostgreSQL sequences consistent.
            for t in tables:
                rows = payload['tables'][t.name]
                if t is not store.events:
                    rows = [{k: v for k, v in row.items() if k != 'id'} for row in rows]
                if rows:
                    conn.execute(t.insert(), rows)
        print('Restored in read-only execution mode. Collector remains disconnected.')


if __name__ == '__main__':
    main()

import hashlib
import json
import os
from pathlib import Path

from sqlalchemy import select


ROOT = Path(os.environ.get('LEGACY_DATA_DIR', Path(__file__).resolve().parents[1]))
PUBLIC_FIELDS = {'market', 'action', 'reason', 'strategy_label', 'strategy_name', 'amount', 'volume',
                 'price', 'score', 'count', 'market_regime', 'operation_mode', 'trading_style'}


def read_json(name, default=None):
    try:
        return json.loads((ROOT / name).read_text(encoding='utf-8-sig'))
    except (OSError, ValueError):
        return default if default is not None else {}


def import_history(store, path=None):
    path = path or ROOT / 'trade_history.jsonl'
    imported = invalid = 0
    if not path.exists():
        return {'imported': 0, 'invalid': 0}
    with store.engine.begin() as conn, path.open(encoding='utf-8-sig') as file:
        for index, line in enumerate(file):
            try:
                row = json.loads(line)
                if not isinstance(row, dict):
                    raise ValueError()
                payload = {k: v for k, v in row.items() if k in PUBLIC_FIELDS}
                # Preserve repeated identical records while making re-import idempotent.
                key = hashlib.sha256(f'legacy-v1:{index}:{line.strip()}'.encode()).hexdigest()
                if not conn.execute(select(store.events.c.id).where(store.events.c.id == key)).first():
                    conn.execute(store.events.insert().values(id=key, time=str(row.get('time', '')),
                                 kind=str(row.get('event', 'unknown')), payload=payload))
                    imported += 1
            except (ValueError, TypeError):
                invalid += 1
    return {'imported': imported, 'invalid': invalid}

import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import JSON, Column, Integer, MetaData, String, Table, create_engine, select


def now():
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, url=None):
        root = Path(os.environ.get('NEURAL_DATA_DIR', Path(__file__).resolve().parents[1] / 'next_data'))
        root.mkdir(parents=True, exist_ok=True)
        secret_file = os.environ.get('DATABASE_URL_FILE')
        secret_url = Path(secret_file).read_text().strip() if secret_file else None
        self.engine = create_engine(url or secret_url or os.environ.get('DATABASE_URL', f'sqlite:///{root / "neural.db"}'))
        meta = MetaData()
        self.events = Table('source_events', meta, Column('id', String(64), primary_key=True),
                            Column('time', String), Column('kind', String), Column('payload', JSON))
        self.snapshots = Table('account_snapshots', meta, Column('id', Integer, primary_key=True),
                              Column('time', String), Column('account', String), Column('payload', JSON))
        self.drafts = Table('config_drafts', meta, Column('id', Integer, primary_key=True),
                           Column('time', String), Column('scope', String), Column('payload', JSON))
        self.health = Table('collector_health', meta, Column('account', String, primary_key=True),
                            Column('time', String), Column('status', String))
        meta.create_all(self.engine)

    def add_snapshot(self, payload, account='upbit'):
        with self.engine.begin() as conn:
            conn.execute(self.snapshots.insert().values(time=payload['as_of'], account=account, payload=payload))

    def set_health(self, status, account='upbit'):
        with self.engine.begin() as conn:
            conn.execute(self.health.delete().where(self.health.c.account == account))
            conn.execute(self.health.insert().values(account=account, time=now(), status=status))

    def latest(self, account='upbit'):
        with self.engine.connect() as conn:
            return conn.execute(select(self.snapshots.c.payload)
                                .where(self.snapshots.c.account == account)
                                .order_by(self.snapshots.c.id.desc()).limit(1)).scalar()

    def history(self, account='upbit'):
        with self.engine.connect() as conn:
            values = conn.execute(select(self.snapshots.c.payload)
                                  .where(self.snapshots.c.account == account)
                                  .order_by(self.snapshots.c.id.desc()).limit(300)).scalars().all()
        return [{'as_of': v['as_of'], 'equity': v['equity']} for v in reversed(values)]

    def collector_status(self, account='upbit'):
        with self.engine.connect() as conn:
            row = conn.execute(select(self.health).where(self.health.c.account == account)).mappings().first()
        return dict(row) if row else {'status': 'not_connected', 'time': None}

    def event_list(self):
        with self.engine.connect() as conn:
            return [dict(r) for r in conn.execute(select(self.events).order_by(self.events.c.time.desc(), self.events.c.id).limit(300)).mappings()]

    def add_draft(self, scope, payload):
        with self.engine.begin() as conn:
            result = conn.execute(self.drafts.insert().values(time=now(), scope=scope, payload=payload))
            return result.inserted_primary_key[0]

    def draft_list(self):
        with self.engine.connect() as conn:
            return [dict(r) for r in conn.execute(select(self.drafts).order_by(self.drafts.c.id.desc()).limit(50)).mappings()]

import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from neural.legacy import read_json
from neural.store import Store
from neural.strategy_lab import CATALOG, demo_reports


class Draft(BaseModel):
    scope: Literal['trading', 'notifications', 'universe']
    mode: Literal['analysis', 'approval', 'automatic'] = 'approval'
    buy_amount: float = Field(default=20000, ge=5000, le=10000000)
    interval: Literal['1m', '3m', '5m'] = '3m'
    leverage: int = Field(default=2, ge=1, le=2)
    report_minutes: int = Field(default=5, ge=1, le=1440)
    events: list[Literal['risk', 'fill', 'recommendation', 'summary']] = ['risk', 'fill']
    symbols: list[str] = Field(default_factory=list, max_length=1000)
    group: str = Field(default='watch', max_length=40)


def snapshot_age(snapshot):
    if not snapshot:
        return None
    return max(0, (datetime.now(timezone.utc) - datetime.fromisoformat(snapshot['as_of'])).total_seconds())


def create_app(store=None):
    db = store or Store()
    app = FastAPI(title='Neural Trade', docs_url='/api/docs')

    @app.middleware('http')
    async def local_boundary(request: Request, call_next):
        if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            origin = request.headers.get('origin')
            expected = os.environ.get('PUBLIC_BASE_URL', str(request.base_url).rstrip('/'))
            if origin != expected or request.headers.get('x-neural-client') != 'dashboard':
                from fastapi.responses import JSONResponse
                return JSONResponse({'detail': 'invalid_origin'}, status_code=403)
        result = await call_next(request)
        result.headers['X-Content-Type-Options'] = 'nosniff'
        result.headers['X-Frame-Options'] = 'DENY'
        result.headers['Cache-Control'] = 'no-store'
        return result

    @app.get('/api/v1/health')
    def health():
        return {'service': 'neural-dashboard', 'execution': 'read_only', 'database': 'connected'}

    @app.get('/api/v1/overview')
    def overview():
        upbit_snapshot = db.latest('upbit')
        futures_snapshot = db.latest('binance_futures')
        upbit_status = db.collector_status('upbit')
        futures_status = db.collector_status('binance_futures')
        age = snapshot_age(upbit_snapshot)
        runtime = read_json('runtime_state.json')
        settings = read_json('trading_settings.json')
        rec = read_json('recommendation_state.json')
        allowed = {'operation_mode', 'trading_style', 'approval_required', 'buy_amount_krw',
                   'max_positions', 'max_daily_trades', 'stop_loss_rate', 'min_recommendation_score'}
        return {
            'snapshot': upbit_snapshot, 'age_seconds': age, 'stale': age is None or age > 90,
            'collector': upbit_status, 'scope': '연결된 계좌만 합산',
            'accounts': {
                'upbit': {'snapshot': upbit_snapshot, 'history': db.history('upbit'),
                          'collector': upbit_status},
                'binance_futures': {'snapshot': futures_snapshot,
                                    'history': db.history('binance_futures'),
                                    'collector': futures_status},
            },
            'connections': [
                {'id': 'upbit', 'label': 'Upbit 현물', 'status': upbit_status['status']},
                {'id': 'stock', 'label': '국내주식', 'status': 'not_configured'},
                {'id': 'futures', 'label': 'Binance USD-M 선물', 'status': futures_status['status']},
            ],
            'runtime': {k: runtime.get(k) for k in
                        ['last_heartbeat', 'paused', 'dry_run', 'real_trade_enabled']},
            'settings': {k: v for k, v in settings.items() if k in allowed},
            'recommendations': rec.get('recommendations', []),
            'recommendations_as_of': rec.get('generated_at'),
            'regime': rec.get('market_regime'), 'history': db.history('upbit'),
        }

    @app.get('/api/v1/events')
    def events():
        return db.event_list()

    @app.get('/api/v1/universe')
    def universe():
        return read_json('coin_registry.json')

    @app.get('/api/v1/drafts')
    def drafts():
        return db.draft_list()

    @app.get('/api/v1/strategies')
    def strategies():
        return {'catalog': CATALOG, 'demo': demo_reports(),
                'execution': 'offline_research_only'}

    @app.post('/api/v1/drafts', status_code=201)
    def save_draft(draft: Draft):
        number = db.add_draft(draft.scope, draft.model_dump())
        return {'id': number, 'state': 'DRAFT', 'applied': False}

    @app.post('/api/v1/commands')
    def commands():
        raise HTTPException(409, '거래 실행기는 아직 연결되지 않았습니다.')

    @app.websocket('/api/v1/events/live')
    async def stream(websocket: WebSocket):
        expected = os.environ.get('PUBLIC_BASE_URL', f'http://{websocket.headers.get("host")}')
        if websocket.headers.get('origin') != expected:
            await websocket.close(code=1008)
            return
        await websocket.accept()
        try:
            while True:
                await websocket.send_json(await asyncio.to_thread(overview))
                await asyncio.sleep(5)
        except Exception:
            return

    dist = Path(__file__).resolve().parents[1] / 'apps/dashboard/dist'
    if dist.exists():
        app.mount('/assets', StaticFiles(directory=dist / 'assets'), name='assets')

        @app.get('/')
        def home():
            return FileResponse(dist / 'index.html')
    return app

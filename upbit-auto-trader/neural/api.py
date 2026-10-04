import asyncio
import os
import re
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
from runtime_state import set_command


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


class ControlCommand(BaseModel):
    action: Literal['pause', 'kill']


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

    @app.get('/api/v1/paper')
    def paper():
        from neural.paper import report
        return report()

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

    @app.get('/api/v1/terminal')
    def terminal():
        """Return a bounded, read-only view of operational logs."""
        root = Path(__file__).resolve().parents[1]
        files = {
            'Upbit 실거래': root / 'next_data/logs/launchd-upbit-worker.out.log',
            'Upbit 오류': root / 'next_data/logs/launchd-upbit-worker.err.log',
            'Binance 실거래': root / 'next_data/logs/launchd-binance-live.out.log',
            '대시보드': root / 'next_data/logs/launchd-api.err.log',
        }
        ansi = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
        sections = []
        for label, path in files.items():
            try:
                lines = path.read_text(encoding='utf-8', errors='replace').splitlines()[-80:]
            except FileNotFoundError:
                lines = ['기록 파일이 아직 없습니다.']
            sections.append({'label': label, 'text': ansi.sub('', '\n'.join(lines)),
                             'updated_at': datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
                             if path.exists() else None})
        return {'mode': 'read_only', 'sections': sections,
                'as_of': datetime.now(timezone.utc).isoformat()}

    @app.get('/api/v1/universe')
    def universe():
        return read_json('coin_registry.json')

    _kiwoom_cache: dict = {'as_of': None, 'data': None}

    @app.get('/api/v1/kiwoom/rankings')
    def kiwoom_rankings():
        """국내주식 당일 동향(등락률/거래량 상위) — 읽기 전용, 주문 없음.

        Kiwoom rate limits are unverified, so results are cached in-process
        for 30s instead of hitting the API on every dashboard poll.
        """
        now = datetime.now(timezone.utc)
        cached = _kiwoom_cache['data']
        if cached and (now - _kiwoom_cache['as_of']).total_seconds() < 30:
            return cached

        from config import Config
        from kiwoom_client import KiwoomAPIError, KiwoomClient

        config = Config.load(Path(__file__).resolve().parents[1] / '.env')
        if not config.kiwoom_app_key or not config.kiwoom_app_secret:
            result = {'as_of': now.isoformat(), 'connected': False,
                      'error': 'KIWOOM_APP_KEY/SECRET이 설정되지 않았습니다.',
                      'top_change': [], 'top_volume': []}
            _kiwoom_cache.update(as_of=now, data=result)
            return result

        client = KiwoomClient(app_key=config.kiwoom_app_key, app_secret=config.kiwoom_app_secret,
                               base_url=config.kiwoom_base_url)
        try:
            top_change = client.get_top_change_rate()
            top_volume = client.get_top_volume_today()
            result = {'as_of': now.isoformat(), 'connected': True, 'error': None,
                      'top_change': top_change[:15], 'top_volume': top_volume[:15]}
        except KiwoomAPIError as exc:
            result = {'as_of': now.isoformat(), 'connected': False, 'error': str(exc)[:300],
                      'top_change': [], 'top_volume': []}
        _kiwoom_cache.update(as_of=now, data=result)
        return result

    _orderbook_cache: dict = {}

    @app.get('/api/v1/kiwoom/orderbook')
    def kiwoom_orderbook(code: str = '005930'):
        """개별 종목 10호가 — 읽기 전용, 주문 없음.

        REST 스냅샷이라 진짜 웹소켓 실시간은 아니다. 3초 캐시로 폴링에
        맞춘다(프론트도 같은 주기로 다시 부른다).
        """
        code = re.sub(r'[^0-9]', '', code)[:6] or '005930'
        now = datetime.now(timezone.utc)
        cached = _orderbook_cache.get(code)
        if cached and (now - cached['as_of']).total_seconds() < 3:
            return cached['data']

        from config import Config
        from kiwoom_client import KiwoomAPIError, KiwoomClient

        config = Config.load(Path(__file__).resolve().parents[1] / '.env')
        if not config.kiwoom_app_key or not config.kiwoom_app_secret:
            result = {'as_of': now.isoformat(), 'connected': False,
                      'error': 'KIWOOM_APP_KEY/SECRET이 설정되지 않았습니다.',
                      'stk_cd': code, 'base_time': '', 'asks': [], 'bids': [],
                      'total_ask_qty': '0', 'total_bid_qty': '0'}
            _orderbook_cache[code] = {'as_of': now, 'data': result}
            return result

        client = KiwoomClient(app_key=config.kiwoom_app_key, app_secret=config.kiwoom_app_secret,
                               base_url=config.kiwoom_base_url)
        try:
            book = client.get_order_book(code)
            result = {'as_of': now.isoformat(), 'connected': True, 'error': None, **book}
        except KiwoomAPIError as exc:
            result = {'as_of': now.isoformat(), 'connected': False, 'error': str(exc)[:300],
                      'stk_cd': code, 'base_time': '', 'asks': [], 'bids': [],
                      'total_ask_qty': '0', 'total_bid_qty': '0'}
        _orderbook_cache[code] = {'as_of': now, 'data': result}
        return result

    @app.get('/api/v1/drafts')
    def drafts():
        return db.draft_list()

    @app.get('/api/v1/strategies')
    def strategies():
        return {'catalog': CATALOG, 'demo': demo_reports(),
                'execution': 'offline_research_only'}

    @app.post('/api/v1/drafts')
    def save_draft(draft: Draft):
        raise HTTPException(403, '전략과 그룹은 자동 루프가 관리합니다.')

    @app.post('/api/v1/commands')
    def commands(command: ControlCommand):
        state = set_command(command.action, 'neural_dashboard')
        return {'accepted': True, 'action': command.action, 'paused': state.paused,
                'kill_switch': state.kill_switch, 'updated_at': state.last_updated}

    @app.websocket('/api/v1/events/live')
    async def stream(websocket: WebSocket):
        host = websocket.headers.get('host')
        allowed_origins = {
            os.environ.get('PUBLIC_BASE_URL', ''),
            f'http://{host}',
            f'https://{host}',
        }
        if websocket.headers.get('origin') not in allowed_origins:
            await websocket.close(code=1008)
            return
        await websocket.accept()
        try:
            while True:
                payload = await asyncio.gather(
                    asyncio.to_thread(overview),
                    asyncio.to_thread(terminal),
                    asyncio.to_thread(events),
                )
                await websocket.send_json({
                    'overview': payload[0],
                    'terminal': payload[1],
                    'events': payload[2],
                    'streamed_at': datetime.now(timezone.utc).isoformat(),
                })
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

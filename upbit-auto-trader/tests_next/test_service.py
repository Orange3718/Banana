import json
import httpx
from pathlib import Path

from fastapi.testclient import TestClient

from neural.api import create_app
from neural.collector import normalize
from neural.binance_futures import normalize as normalize_futures, signed_params
from neural.legacy import import_history
from neural.store import Store
from neural.preflight import report as preflight_report
from neural.strategy_lab import CATALOG, backtest, demo_reports, sample_candles


def store(tmp_path):
    return Store(f'sqlite:///{tmp_path / "test.db"}')


def test_all_holdings_and_locked_cash():
    result = normalize([
        {'currency': 'KRW', 'balance': '100', 'locked': '20'},
        {'currency': 'ETH', 'balance': '1', 'locked': '0.5', 'avg_buy_price': '10', 'unit_currency': 'KRW'},
        {'currency': 'BTC', 'balance': '2', 'locked': '0', 'avg_buy_price': '20', 'unit_currency': 'KRW'},
    ], [{'market': 'KRW-ETH', 'trade_price': '15'}, {'market': 'KRW-BTC', 'trade_price': '25'}])
    assert result['equity'] == '192.5'
    assert result['unrealized'] == '17.5'
    assert len(result['positions']) == 2


def test_bom_env_keeps_access_key_name(tmp_path):
    from dotenv import dotenv_values
    file = tmp_path / '.env'
    file.write_text('\ufeffUPBIT_ACCESS_KEY=abc\nUPBIT_SECRET_KEY=def\n', encoding='utf-8')
    values = dotenv_values(file, encoding='utf-8-sig')
    assert values['UPBIT_ACCESS_KEY'] == 'abc'


def test_binance_futures_normalization():
    result = normalize_futures({
        'availableBalance': '80', 'totalMarginBalance': '110',
        'totalUnrealizedProfit': '10',
        'positions': [
            {'symbol': 'ETHUSDT', 'positionAmt': '-2', 'entryPrice': '55',
             'notional': '-120', 'unrealizedProfit': '10', 'positionSide': 'BOTH',
             'leverage': '2', 'isolated': False},
            {'symbol': 'BTCUSDT', 'positionAmt': '0'},
        ],
    }, [{'symbol': 'ETHUSDT', 'markPrice': '60'}])
    assert result['currency'] == 'USD'
    assert result['equity'] == '110'
    assert result['positions'][0]['quantity'] == '-2'
    assert result['positions'][0]['value'] == '120'
    assert result['positions'][0]['price'] == '60'


def test_binance_signature_is_stable():
    assert signed_params('secret', 1000) == {
        'recvWindow': 5000,
        'timestamp': 1000,
        'signature': '4ab147591dd16c30ece17c433ba5494654026cf4b9337744038cab494f1f4751',
    }


def test_store_separates_exchange_accounts(tmp_path):
    db = store(tmp_path)
    db.add_snapshot({'as_of': '2026-01-01T00:00:00+00:00', 'equity': '10'}, 'upbit')
    db.add_snapshot({'as_of': '2026-01-01T00:00:01+00:00', 'equity': '20'}, 'binance_futures')
    db.set_health('connected', 'upbit')
    db.set_health('disabled', 'binance_futures')
    assert db.latest('upbit')['equity'] == '10'
    assert db.latest('binance_futures')['equity'] == '20'
    assert db.collector_status('binance_futures')['status'] == 'disabled'


def test_preflight_never_exposes_credentials(tmp_path):
    env = tmp_path / '.env'
    env.write_text('UPBIT_ACCESS_KEY=private-a\nUPBIT_SECRET_KEY=private-b\n'
                   'BINANCE_FUTURES_ENABLED=false\n', encoding='utf-8')
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={}))
    result = preflight_report(env, httpx.Client(transport=transport), store(tmp_path))
    rendered = json.dumps(result)
    assert result['credentials']['upbit_configured'] is True
    assert result['credentials']['binance_enabled'] is False
    assert 'private-a' not in rendered
    assert 'private-b' not in rendered


def test_offline_strategy_lab_is_deterministic_and_cost_aware():
    candles = sample_candles()
    first = backtest(candles, 'donchian')
    second = backtest(candles, 'donchian')
    expensive = backtest(candles, 'donchian', fee_rate=.01, slippage_rate=.01)
    assert first == second
    assert first['research_only'] is True
    assert expensive['net_return_pct'] <= first['net_return_pct']


def test_strategy_api_has_no_execution_control(tmp_path):
    client = TestClient(create_app(store(tmp_path)))
    result = client.get('/api/v1/strategies').json()
    assert result['execution'] == 'offline_research_only'
    assert len(result['catalog']) == len(CATALOG) == 3
    assert len(result['demo']['reports']) == 3


def test_unpriced_never_becomes_zero_equity():
    result = normalize([{'currency': 'UNKNOWN', 'balance': '2'}], [])
    assert result['equity'] is None
    assert result['positions'][0]['price'] is None
    assert result['unpriced'] == ['UNKNOWN']


def test_non_krw_cost_is_not_used_as_krw():
    result = normalize([{'currency': 'ETH', 'balance': '1', 'avg_buy_price': '.01', 'unit_currency': 'BTC'}],
                       [{'market': 'KRW-ETH', 'trade_price': 100}])
    assert result['unrealized'] is None


def test_import_idempotent_redacts_and_counts_invalid(tmp_path):
    db = store(tmp_path)
    file = tmp_path / 'history.jsonl'
    row = json.dumps({'event': 'order', 'market': 'KRW-ETH', 'secret_key': 'MUST_NOT_EXPOSE'})
    file.write_text(row + '\n' + row + '\nbroken\n', encoding='utf-8')
    assert import_history(db, file) == {'imported': 2, 'invalid': 1}
    assert import_history(db, file) == {'imported': 0, 'invalid': 1}
    assert 'MUST_NOT_EXPOSE' not in json.dumps(db.event_list())


def test_drafts_do_not_modify_legacy(tmp_path, monkeypatch):
    import neural.legacy as legacy
    monkeypatch.setattr(legacy, 'ROOT', tmp_path)
    file = tmp_path / 'trading_settings.json'
    file.write_text('{"operation_mode": 4}', encoding='utf-8')
    client = TestClient(create_app(store(tmp_path)))
    headers = {'Origin': 'http://testserver', 'X-Neural-Client': 'dashboard'}
    r = client.post('/api/v1/drafts', json={'scope': 'trading'}, headers=headers)
    assert r.status_code == 201
    assert r.json()['applied'] is False
    assert json.loads(file.read_text()) == {'operation_mode': 4}
    assert len(client.get('/api/v1/drafts').json()) == 1
    assert client.post('/api/v1/commands', headers=headers).status_code == 409


def test_origin_and_risk_limits(tmp_path):
    client = TestClient(create_app(store(tmp_path)))
    assert client.post('/api/v1/drafts', json={'scope': 'trading'}).status_code == 403
    assert client.post('/api/v1/drafts', json={'scope': 'trading', 'leverage': 20},
                       headers={'Origin': 'http://testserver', 'X-Neural-Client': 'dashboard'}).status_code == 422


def test_unknown_and_stale_are_explicit(tmp_path, monkeypatch):
    import neural.legacy as legacy
    monkeypatch.setattr(legacy, 'ROOT', tmp_path)
    db = store(tmp_path)
    client = TestClient(create_app(db))
    assert client.get('/api/v1/overview').json()['snapshot'] is None
    db.add_snapshot({'as_of': '2020-01-01T00:00:00+00:00', 'equity': '123'})
    result = client.get('/api/v1/overview').json()
    assert result['stale'] is True
    assert result['connections'][1]['status'] == 'not_configured'


def test_runtime_error_text_is_not_exposed(tmp_path, monkeypatch):
    import neural.legacy as legacy
    monkeypatch.setattr(legacy, 'ROOT', tmp_path)
    (tmp_path / 'runtime_state.json').write_text(
        '{"last_status":"secret-bearing upstream response", "paused":true}', encoding='utf-8')
    result = TestClient(create_app(store(tmp_path))).get('/api/v1/overview').json()
    assert result['runtime']['paused'] is True
    assert 'last_status' not in result['runtime']
    assert 'secret-bearing' not in json.dumps(result)

"""Persistent public-data forward simulation. Never loads exchange credentials."""
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from neural.strategy_lab import Candle, CATALOG, signal


ROOT = Path(os.environ.get('NEURAL_DATA_DIR', Path(__file__).resolve().parents[1] / 'next_data'))
MARKETS = [('upbit', s) for s in ('KRW-BTC', 'KRW-ETH', 'KRW-SOL')] + [
    ('binance', s) for s in ('SAMSUNGUSDT', 'SKHYNIXUSDT')]


def connect(path=None):
    ROOT.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path or ROOT / 'paper.db', timeout=30)
    db.execute('PRAGMA journal_mode=WAL')
    db.execute('CREATE TABLE IF NOT EXISTS portfolios (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    db.execute('CREATE TABLE IF NOT EXISTS health (id TEXT PRIMARY KEY, payload TEXT NOT NULL)')
    return db


def candles(client, exchange, symbol):
    if exchange == 'upbit':
        response = client.get('https://api.upbit.com/v1/candles/minutes/60',
                              params={'market': symbol, 'count': 200})
        response.raise_for_status()
        rows = [Candle(str(int(datetime.fromisoformat(r['candle_date_time_utc']).replace(
            tzinfo=timezone.utc).timestamp())), r['opening_price'], r['high_price'],
            r['low_price'], r['trade_price'], r['candle_acc_trade_volume']) for r in response.json()]
    else:
        response = client.get('https://fapi.binance.com/fapi/v1/klines',
                              params={'symbol': symbol, 'interval': '1h', 'limit': 200})
        response.raise_for_status()
        rows = [Candle(str(int(r[0]) // 1000), *map(float, r[1:6])) for r in response.json()]
    rows.sort(key=lambda r: int(r.time))
    rows = [r for r in rows if int(r.time) + 3600 <= time.time()]
    if len(rows) < 65 or time.time() - (int(rows[-1].time) + 3600) > 3900:
        raise ValueError('missing_or_stale_candles')
    if any(int(b.time) - int(a.time) != 3600 for a, b in zip(rows, rows[1:])):
        raise ValueError('candle_gap')
    if any(not (0 < r.low <= min(r.open, r.close) <= max(r.open, r.close) <= r.high)
           or r.volume < 0 for r in rows):
        raise ValueError('invalid_ohlcv')
    return rows


def advance(state, rows, price, strategy, exchange):
    """At most one decision per closed bar; fills use a subsequently observed quote."""
    initial = 1_000_000 if exchange == 'upbit' else 1000
    if state is None:
        state = dict(initial=initial, cash=initial, quantity=0, entry=0, cost=0,
                     peak=initial, drawdown=0, realized=0, fees=0, trades=0, wins=0,
                     last=rows[-1].time, day='', day_start=initial, halted=False, events=[])
        state['reason'] = '초기화 완료 · 다음 완료 봉 대기'
    elif state['last'] != rows[-1].time:
        equity = state['cash'] + state['quantity'] * price
        day = datetime.now(timezone.utc).date().isoformat()
        if state['day'] != day:
            state.update(day=day, day_start=equity, halted=False)
        state['halted'] |= equity <= state['day_start'] * .98 or equity <= state['initial'] * .9
        action, reason = signal(strategy, rows, len(rows) - 1, state['quantity'] > 0)
        if state['quantity'] and (price <= state['entry'] * .975 or state['halted']):
            action, reason = 'SELL', '손실 보호 청산'
        fee, slip = .001, .001  # Assumptions, not account-specific exchange rates.
        if action == 'BUY' and not state['halted'] and not state['quantity']:
            cost = state['cash'] * .2
            fill = price * (1 + slip)
            state.update(cash=state['cash'] - cost, quantity=cost / (1 + fee) / fill,
                         entry=fill, cost=cost)
            state['fees'] += cost - cost / (1 + fee)
        elif action == 'SELL' and state['quantity']:
            gross = state['quantity'] * price * (1 - slip)
            net = gross * (1 - fee)
            pnl = net - state['cost']
            state['cash'] += net
            state['realized'] += pnl
            state['fees'] += gross * fee
            state['trades'] += 1
            state['wins'] += int(pnl > 0)
            state.update(quantity=0, entry=0, cost=0)
        else:
            action = 'HOLD'
        state['events'] = (state['events'] + [dict(time=datetime.now(timezone.utc).isoformat(),
            action=action, price=price, reason=reason)])[-100:]
        state.update(last=rows[-1].time, reason=reason)
    equity = state['cash'] + state['quantity'] * price
    state['peak'] = max(state['peak'], equity)
    state['drawdown'] = min(state['drawdown'], (equity / state['peak'] - 1) * 100)
    state.update(equity=equity, return_pct=(equity / initial - 1) * 100,
                 as_of=datetime.now(timezone.utc).isoformat(), price=price)
    return state


def cycle(db, client):
    for exchange, symbol in MARKETS:
        key = exchange + ':' + symbol
        try:
            rows = candles(client, exchange, symbol)
            url, params = ('https://api.upbit.com/v1/ticker', {'markets': symbol}) if exchange == 'upbit' else (
                'https://fapi.binance.com/fapi/v1/ticker/price', {'symbol': symbol})
            response = client.get(url, params=params)
            response.raise_for_status()
            price = float(response.json()[0]['trade_price'] if exchange == 'upbit' else response.json()['price'])
            if not 0 < price < float('inf'):
                raise ValueError('invalid_price')
            with db:
                for strategy in CATALOG:
                    identity = key + ':' + strategy['id']
                    row = db.execute('SELECT payload FROM portfolios WHERE id=?', (identity,)).fetchone()
                    state = advance(json.loads(row[0]) if row else None, rows, price, strategy['id'], exchange)
                    state.update(symbol=symbol, exchange=exchange, strategy=strategy['name'],
                                 currency='KRW' if exchange == 'upbit' else 'USDT',
                                 funding_included=False)
                    db.execute('INSERT OR REPLACE INTO portfolios VALUES (?,?)', (identity, json.dumps(state)))
            status = 'connected'
        except Exception as exc:
            status = 'error:' + type(exc).__name__
        with db:
            db.execute('INSERT OR REPLACE INTO health VALUES (?,?)', (key, json.dumps(dict(
                status=status, as_of=datetime.now(timezone.utc).isoformat()))))


def report():
    db = connect()
    try:
        return dict(mode='PAPER', interval='1h', fee_pct=.1, slippage_pct=.1,
                    funding_included=False, portfolios=[json.loads(r[0]) for r in db.execute(
                        'SELECT payload FROM portfolios ORDER BY id')],
                    health={r[0]: json.loads(r[1]) for r in db.execute('SELECT id,payload FROM health')})
    finally:
        db.close()


def run():
    import fcntl
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / 'paper.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        db = connect()
        with httpx.Client(timeout=15) as client:
            while True:
                cycle(db, client)
                time.sleep(60)


if __name__ == '__main__':
    run()

"""Small, bounded Binance USD-M live executor for BTCUSDT.

The worker evaluates a fee-aware hourly breakout once per completed candle,
keeps at most one 0.001 BTC isolated 1x position, and requires an
exchange-hosted stop order.
"""
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN, ROUND_UP
from pathlib import Path
from urllib.parse import urlencode

import httpx
from dotenv import dotenv_values
from runtime_state import load_state as load_runtime_state


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'next_data'
STATE_PATH = DATA / 'binance_live_state.json'
SYMBOL = 'BTCUSDT'
QUANTITY = Decimal('0.001')
STOP_RATE = Decimal('0.02')
ENTRY_LOOKBACK = 24
EXIT_LOOKBACK = 12
ENTRY_COOLDOWN_SECONDS = 60 * 60
DAILY_LOSS_LIMIT = Decimal('3')
MAX_CONSECUTIVE_LOSSES = 3
LOSS_STREAK_COOLDOWN_SECONDS = int(os.environ.get('BINANCE_LOSS_STREAK_COOLDOWN_SECONDS',
                                                   str(6 * 60 * 60)))


def emit(event, **values):
    print(json.dumps({'time': datetime.now(timezone.utc).isoformat(), 'event': event,
                      **values}, ensure_ascii=False), flush=True)


def load_state():
    try:
        state = json.loads(STATE_PATH.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        return {'last_candle': None, 'entry_time': None, 'entry_side': None,
                'entry_order': None, 'entry_price': None,
                'consecutive_losses': 0, 'last_close_order': None,
                'last_close_time': None, 'last_loss_time': None}
    state.setdefault('last_close_time', None)
    state.setdefault('last_loss_time', None)
    state.setdefault('entry_order', None)
    state.setdefault('entry_price', None)
    if state.get('consecutive_losses', 0) >= MAX_CONSECUTIVE_LOSSES and not state['last_loss_time']:
        try:
            state['last_loss_time'] = int(STATE_PATH.stat().st_mtime)
        except OSError:
            state['last_loss_time'] = int(time.time())
    return state


def save_state(state):
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = STATE_PATH.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    tmp.replace(STATE_PATH)


def loss_streak_blocked(state, now=None):
    if state.get('consecutive_losses', 0) < MAX_CONSECUTIVE_LOSSES:
        return False
    now = int(now or time.time())
    last_loss_time = state.get('last_loss_time')
    if last_loss_time and now - int(last_loss_time) >= LOSS_STREAK_COOLDOWN_SECONDS:
        state.update(consecutive_losses=0, last_loss_time=None)
        save_state(state)
        emit('loss_streak_reset', cooldown_seconds=LOSS_STREAK_COOLDOWN_SECONDS)
        return False
    return True


def ema(values, period):
    alpha = Decimal(2) / Decimal(period + 1)
    value = values[0]
    for item in values:
        value = alpha * item + (Decimal(1) - alpha) * value
    return value


def breakout_signal(hourly, four_hour):
    """Return the decision made from completed candles only."""
    if len(hourly) < ENTRY_LOOKBACK + 1 or len(four_hour) < 50:
        raise RuntimeError('insufficient completed candles')
    regime_closes = [Decimal(row[4]) for row in four_hour]
    regime = 'LONG' if ema(regime_closes, 20) > ema(regime_closes, 50) else 'SHORT'
    latest = hourly[-1]
    previous_entry = hourly[-ENTRY_LOOKBACK - 1:-1]
    previous_exit = hourly[-EXIT_LOOKBACK - 1:-1]
    close = Decimal(latest[4])
    entry = None
    if regime == 'LONG' and close > max(Decimal(row[2]) for row in previous_entry):
        entry = 'LONG'
    elif regime == 'SHORT' and close < min(Decimal(row[3]) for row in previous_entry):
        entry = 'SHORT'
    return {
        'candle': int(latest[6]),
        'close': close,
        'regime': regime,
        'entry': entry,
        'exit_long': close < min(Decimal(row[3]) for row in previous_exit),
        'exit_short': close > max(Decimal(row[2]) for row in previous_exit),
    }


class Binance:
    def __init__(self):
        config = dotenv_values(ROOT / '.env', encoding='utf-8-sig')
        self.key = config.get('BINANCE_API_KEY')
        secret = config.get('BINANCE_SECRET_KEY')
        if not self.key or not secret:
            raise RuntimeError('missing Binance credentials')
        self.secret = secret.encode()
        self.client = httpx.Client(base_url=config.get('BINANCE_FUTURES_BASE_URL',
                                                        'https://fapi.binance.com'), timeout=15)
        self.delta = self.public('/fapi/v1/time')['serverTime'] - int(time.time() * 1000)

    def public(self, path, params=None):
        response = self.client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    def signed(self, method, path, params=None):
        values = dict(params or {})
        values.update(recvWindow=5000, timestamp=int(time.time() * 1000) + self.delta)
        query = urlencode(values)
        values['signature'] = hmac.new(self.secret, query.encode(), hashlib.sha256).hexdigest()
        response = self.client.request(method, path, params=values,
                                       headers={'X-MBX-APIKEY': self.key})
        response.raise_for_status()
        return response.json() if response.content else {}

    def position(self):
        rows = self.signed('GET', '/fapi/v2/positionRisk', {'symbol': SYMBOL})
        return next(row for row in rows if row['symbol'] == SYMBOL and
                    row.get('positionSide', 'BOTH') == 'BOTH')

    def algos(self):
        return self.signed('GET', '/fapi/v1/openAlgoOrders', {'symbol': SYMBOL})

    def cancel_algos(self):
        for order in self.algos():
            self.signed('DELETE', '/fapi/v1/algoOrder', {'algoId': order['algoId']})
            emit('protection_cancelled', algo_id=order['algoId'])

    def close(self, state, reason):
        position = self.position()
        amount = Decimal(position['positionAmt'])
        if amount == 0:
            self.cancel_algos()
            return
        self.cancel_algos()
        side = 'SELL' if amount > 0 else 'BUY'
        client_id = 'at_local_exit_' + str(int(time.time() * 1000))
        result = self.signed('POST', '/fapi/v1/order', {
            'symbol': SYMBOL, 'side': side, 'type': 'MARKET',
            'quantity': str(abs(amount)), 'reduceOnly': 'true',
            'newClientOrderId': client_id, 'newOrderRespType': 'RESULT'})
        if Decimal(self.position()['positionAmt']) != 0:
            raise RuntimeError('position remained after close')
        self.record_close(state, reason, result['orderId'])

    def position_pnl(self, state, close_order_id=None):
        start_ms = max(0, int(state.get('entry_time') or time.time()) * 1000 - 60_000)
        trades = []
        for attempt in range(6):
            trades = self.signed('GET', '/fapi/v1/userTrades', {
                'symbol': SYMBOL, 'startTime': start_ms, 'limit': 1000})
            if close_order_id is None or any(
                    int(item['orderId']) == int(close_order_id) for item in trades):
                break
            time.sleep(0.25 * (attempt + 1))
        realized = sum((Decimal(item['realizedPnl']) for item in trades), Decimal())
        fees = sum((Decimal(item['commission']) for item in trades
                    if item['commissionAsset'] == 'USDT'), Decimal())
        funding_rows = self.signed('GET', '/fapi/v1/income', {
            'symbol': SYMBOL, 'incomeType': 'FUNDING_FEE',
            'startTime': start_ms, 'limit': 1000})
        funding = sum((Decimal(item['income']) for item in funding_rows
                       if item.get('asset') == 'USDT'), Decimal())
        return realized - fees + funding

    def record_close(self, state, reason, order_id=None):
        pnl = self.position_pnl(state, order_id)
        now_ts = int(time.time())
        state['consecutive_losses'] = state.get('consecutive_losses', 0) + 1 if pnl < 0 else 0
        state['last_loss_time'] = now_ts if pnl < 0 else None
        state.update(entry_time=None, entry_side=None, entry_order=None, entry_price=None,
                     last_close_order=order_id, last_close_time=now_ts)
        save_state(state)
        emit('position_closed', reason=reason, order_id=order_id, net_pnl=str(pnl),
             consecutive_losses=state['consecutive_losses'])

    def daily_net(self):
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0,
                                                   microsecond=0)
        income = self.signed('GET', '/fapi/v1/income', {
            'symbol': SYMBOL, 'startTime': int(start.timestamp() * 1000), 'limit': 1000})
        return sum((Decimal(item['income']) for item in income
                    if item.get('asset') == 'USDT'), Decimal())

    def candles(self, interval, limit=61):
        return self.public('/fapi/v1/klines', {'symbol': SYMBOL, 'interval': interval,
                                               'limit': limit})[:-1]

    def strategy(self):
        return breakout_signal(self.candles('1h'), self.candles('4h'))

    def protect(self, side, entry):
        info = self.public('/fapi/v1/exchangeInfo')
        symbol = next(x for x in info['symbols'] if x['symbol'] == SYMBOL)
        tick = Decimal(next(x['tickSize'] for x in symbol['filters']
                            if x['filterType'] == 'PRICE_FILTER'))
        if side == 'LONG':
            stop = (entry * (1 - STOP_RATE) / tick).to_integral_value(rounding=ROUND_DOWN) * tick
            close_side = 'SELL'
        else:
            stop = (entry * (1 + STOP_RATE) / tick).to_integral_value(rounding=ROUND_UP) * tick
            close_side = 'BUY'
        created = []
        try:
            for order_type, trigger, label in (
                    ('STOP_MARKET', stop, 'stop'),):
                result = self.signed('POST', '/fapi/v1/algoOrder', {
                    'algoType': 'CONDITIONAL', 'symbol': SYMBOL, 'side': close_side,
                    'positionSide': 'BOTH', 'type': order_type,
                    'triggerPrice': str(trigger), 'closePosition': 'true',
                    'workingType': 'MARK_PRICE', 'priceProtect': 'false',
                    'clientAlgoId': 'at_local_' + label + '_' + str(int(time.time() * 1000))})
                created.append(result['algoId'])
            active = {x['algoId'] for x in self.algos()}
            if not set(created).issubset(active):
                raise RuntimeError('protection verification failed')
            return stop
        except Exception:
            for algo_id in created:
                try:
                    self.signed('DELETE', '/fapi/v1/algoOrder', {'algoId': algo_id})
                except Exception:
                    pass
            raise

    def enter(self, state, side):
        self.signed('POST', '/fapi/v1/leverage', {'symbol': SYMBOL, 'leverage': 1})
        try:
            self.signed('POST', '/fapi/v1/marginType', {'symbol': SYMBOL,
                                                        'marginType': 'ISOLATED'})
        except httpx.HTTPStatusError as exc:
            if exc.response.json().get('code') != -4046:
                raise
        order_side = 'BUY' if side == 'LONG' else 'SELL'
        result = self.signed('POST', '/fapi/v1/order', {
            'symbol': SYMBOL, 'side': order_side, 'type': 'MARKET',
            'quantity': str(QUANTITY), 'newOrderRespType': 'RESULT',
            'newClientOrderId': 'at_local_entry_' + str(int(time.time() * 1000))})
        position = self.position()
        try:
            stop = self.protect(side, Decimal(position['entryPrice']))
        except Exception:
            self.close(state, 'protection_failed')
            raise
        state.update(entry_time=int(time.time()), entry_side=side,
                     entry_order=result['orderId'], entry_price=position['entryPrice'])
        save_state(state)
        emit('position_opened', side=side, order_id=result['orderId'],
             entry=position['entryPrice'], stop=str(stop))


def cycle(api, state):
    position = api.position()
    amount = Decimal(position['positionAmt'])
    algos = api.algos()
    control = load_runtime_state()
    if control.kill_switch:
        if amount != 0:
            api.close(state, 'kill_switch')
        elif algos:
            api.cancel_algos()
        return
    strategy = api.strategy()
    if amount != 0:
        expected_side = 'LONG' if amount > 0 else 'SHORT'
        if len(algos) != 1 or {x.get('orderType') for x in algos} != {'STOP_MARKET'}:
            api.close(state, 'protection_missing')
            return
        if not state.get('entry_time'):
            state.update(entry_time=int(time.time()), entry_side=expected_side)
            save_state(state)
        should_exit = (expected_side == 'LONG' and strategy['exit_long']) or (
            expected_side == 'SHORT' and strategy['exit_short'])
        if should_exit:
            api.close(state, 'channel_exit')
        return
    if algos:
        api.cancel_algos()
    if state.get('entry_time'):
        api.record_close(state, 'exchange_protection')
    if control.paused:
        return
    if state.get('last_candle') == strategy['candle']:
        return
    state['last_candle'] = strategy['candle']
    save_state(state)
    emit('strategy_evaluated', candle=strategy['candle'], close=str(strategy['close']),
         regime=strategy['regime'], entry=strategy['entry'])
    if api.daily_net() <= -DAILY_LOSS_LIMIT or loss_streak_blocked(state):
        return
    if state.get('last_close_time') and (
            time.time() - state['last_close_time'] < ENTRY_COOLDOWN_SECONDS):
        return
    if strategy['entry']:
        api.enter(state, strategy['entry'])


def run():
    import fcntl
    DATA.mkdir(parents=True, exist_ok=True)
    with (DATA / 'binance_live.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        api = Binance()
        state = load_state()
        emit('worker_started', symbol=SYMBOL, quantity=str(QUANTITY))
        while True:
            try:
                cycle(api, state)
            except Exception as exc:
                emit('cycle_failed', error=type(exc).__name__, detail=str(exc)[:300])
            if os.environ.get('BINANCE_LIVE_ONCE') == 'true':
                return
            time.sleep(60)


if __name__ == '__main__':
    run()

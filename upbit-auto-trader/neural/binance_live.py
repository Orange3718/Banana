"""Small, bounded Binance USD-M live executor for a liquid-symbol whitelist.

The worker evaluates a fee-aware hourly breakout once per completed candle,
keeps at most one isolated 1x position across the account, and requires an
exchange-hosted stop.
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
SYMBOLS = tuple(dict.fromkeys(
    value.strip().upper()
    for value in os.environ.get(
        'BINANCE_LIVE_SYMBOLS', 'BTCUSDT,SOLUSDT').split(',')
    if value.strip()
))
if not SYMBOLS:
    raise RuntimeError('BINANCE_LIVE_SYMBOLS must contain at least one symbol')
SYMBOL = SYMBOLS[0]
TARGET_NOTIONAL = Decimal(os.environ.get('BINANCE_TARGET_NOTIONAL_USDT', '425'))
STOP_RATE = Decimal(os.environ.get('BINANCE_STOP_RATE', '0.025'))
ENTRY_LOOKBACK = int(os.environ.get('BINANCE_ENTRY_LOOKBACK', '24'))
EXIT_LOOKBACK = int(os.environ.get('BINANCE_EXIT_LOOKBACK', '24'))
ENTRY_CONFIRMATION_RATE = Decimal(os.environ.get(
    'BINANCE_ENTRY_CONFIRMATION_RATE',
    os.environ.get('BINANCE_ENTRY_BUFFER_RATE', '0')))
MIN_REGIME_SPREAD_RATE = Decimal(os.environ.get('BINANCE_MIN_REGIME_SPREAD_RATE', '0.005'))
ALLOW_SHORT = os.environ.get('BINANCE_ALLOW_SHORT', 'false').lower() == 'true'
BTC_DAILY_EMA_PERIOD = int(os.environ.get('BINANCE_BTC_DAILY_EMA_PERIOD', '100'))
TAKER_FEE_RATE = Decimal(os.environ.get('BINANCE_TAKER_FEE_RATE', '0.0005'))
RISK_SLIPPAGE_RATE = Decimal(os.environ.get('BINANCE_RISK_SLIPPAGE_RATE', '0.0002'))
# An already-open position keeps the exit window active when it was entered.
ACTIVE_POSITION_EXIT_LOOKBACK = int(os.environ.get(
    'BINANCE_ACTIVE_POSITION_EXIT_LOOKBACK', str(EXIT_LOOKBACK)))
ENTRY_COOLDOWN_SECONDS = int(os.environ.get('BINANCE_ENTRY_COOLDOWN_SECONDS', '3600'))
DAILY_LOSS_LIMIT = Decimal(os.environ.get('BINANCE_DAILY_LOSS_LIMIT', '15'))
MAX_CONSECUTIVE_LOSSES = int(os.environ.get('BINANCE_MAX_CONSECUTIVE_LOSSES', '3'))
LOSS_STREAK_COOLDOWN_SECONDS = int(os.environ.get('BINANCE_LOSS_STREAK_COOLDOWN_SECONDS',
                                                   str(6 * 60 * 60)))
TIME_SYNC_INTERVAL_SECONDS = int(os.environ.get('BINANCE_TIME_SYNC_INTERVAL_SECONDS', '60'))


def emit(event, **values):
    print(json.dumps({'time': datetime.now(timezone.utc).isoformat(), 'event': event,
                      **values}, ensure_ascii=False), flush=True)


def load_state():
    try:
        state = json.loads(STATE_PATH.read_text(encoding='utf-8'))
    except (FileNotFoundError, json.JSONDecodeError):
        return {'last_candle': None, 'last_candles': {}, 'entry_time': None,
                'entry_symbol': None, 'entry_side': None,
                'entry_order': None, 'entry_price': None,
                'consecutive_losses': 0, 'last_close_order': None,
                'last_close_time': None, 'last_loss_time': None}
    state.setdefault('last_close_time', None)
    state.setdefault('last_loss_time', None)
    state.setdefault('entry_order', None)
    state.setdefault('entry_price', None)
    state.setdefault('entry_symbol', None)
    state.setdefault('last_candles', {})
    if state.get('last_candle') is not None and SYMBOL not in state['last_candles']:
        state['last_candles'][SYMBOL] = state['last_candle']
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


def breakout_signal(hourly, four_hour, *, entry_lookback=None, exit_lookback=None,
                    entry_confirmation_rate=None, min_regime_spread_rate=None,
                    allow_long=True, allow_short=True):
    """Return the decision made from completed candles only."""
    entry_lookback = ENTRY_LOOKBACK if entry_lookback is None else entry_lookback
    exit_lookback = EXIT_LOOKBACK if exit_lookback is None else exit_lookback
    confirmation = (ENTRY_CONFIRMATION_RATE if entry_confirmation_rate is None
                    else Decimal(entry_confirmation_rate))
    min_regime_spread = (MIN_REGIME_SPREAD_RATE if min_regime_spread_rate is None
                         else Decimal(min_regime_spread_rate))
    if len(hourly) < max(entry_lookback, exit_lookback) + 1 or len(four_hour) < 50:
        raise RuntimeError('insufficient completed candles')
    regime_closes = [Decimal(row[4]) for row in four_hour]
    fast_ema = ema(regime_closes, 20)
    slow_ema = ema(regime_closes, 50)
    regime = 'LONG' if fast_ema > slow_ema else 'SHORT'
    latest = hourly[-1]
    previous_entry = hourly[-entry_lookback - 1:-1]
    previous_exit = hourly[-exit_lookback - 1:-1]
    close = Decimal(latest[4])
    regime_spread = abs(fast_ema - slow_ema) / close
    entry = None
    entry_high = max(Decimal(row[2]) for row in previous_entry)
    entry_low = min(Decimal(row[3]) for row in previous_entry)
    entry_strength = Decimal(0)
    if (allow_long and regime_spread >= min_regime_spread and regime == 'LONG' and
            close > entry_high * (Decimal(1) + confirmation)):
        entry = 'LONG'
        entry_strength = close / entry_high - Decimal(1)
    elif (allow_short and regime_spread >= min_regime_spread and regime == 'SHORT' and
          close < entry_low * (Decimal(1) - confirmation)):
        entry = 'SHORT'
        entry_strength = entry_low / close - Decimal(1)
    return {
        'candle': int(latest[6]),
        'close': close,
        'regime': regime,
        'regime_spread': regime_spread,
        'entry': entry,
        'entry_strength': entry_strength,
        'exit_long': close < min(Decimal(row[3]) for row in previous_exit),
        'exit_short': close > max(Decimal(row[2]) for row in previous_exit),
    }


def estimated_worst_case_loss():
    """Conservative loss budget for a new position, including round-trip friction."""
    return TARGET_NOTIONAL * (
        STOP_RATE + Decimal(2) * TAKER_FEE_RATE +
        Decimal(2) * RISK_SLIPPAGE_RATE)


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
        self.delta = 0
        self.last_time_sync = 0.0
        self._exchange_info = None
        self.sync_time()

    def sync_time(self):
        self.delta = self.public('/fapi/v1/time')['serverTime'] - int(time.time() * 1000)
        self.last_time_sync = time.monotonic()

    def public(self, path, params=None):
        response = self.client.get(path, params=params)
        response.raise_for_status()
        return response.json()

    def signed(self, method, path, params=None):
        for attempt in range(2):
            if time.monotonic() - self.last_time_sync >= TIME_SYNC_INTERVAL_SECONDS:
                self.sync_time()
            values = dict(params or {})
            values.update(recvWindow=5000, timestamp=int(time.time() * 1000) + self.delta)
            query = urlencode(values)
            values['signature'] = hmac.new(self.secret, query.encode(), hashlib.sha256).hexdigest()
            response = self.client.request(method, path, params=values,
                                           headers={'X-MBX-APIKEY': self.key})
            try:
                payload = response.json() if response.content else {}
            except ValueError:
                payload = {}
            if (attempt == 0 and response.status_code == 400 and
                    isinstance(payload, dict) and payload.get('code') == -1021):
                self.sync_time()
                continue
            response.raise_for_status()
            return payload
        raise RuntimeError('Binance timestamp resynchronization failed')

    def position(self, symbol=SYMBOL):
        rows = self.signed('GET', '/fapi/v3/positionRisk', {'symbol': symbol})
        position = next((row for row in rows if row['symbol'] == symbol and
                         row.get('positionSide', 'BOTH') == 'BOTH'), None)
        if position is not None:
            return position
        # V3 omits symbols with neither a position nor an open order. Treat
        # that documented response as a flat position so state reconciliation
        # and the next strategy evaluation can continue.
        return {
            'symbol': symbol, 'positionSide': 'BOTH', 'positionAmt': '0',
            'entryPrice': '0', 'markPrice': '0', 'unRealizedProfit': '0',
            'isolatedMargin': '0', 'liquidationPrice': '0', 'notional': '0',
        }

    def positions(self):
        rows = self.signed('GET', '/fapi/v3/positionRisk')
        return [row for row in rows
                if row.get('positionSide', 'BOTH') == 'BOTH' and
                Decimal(row.get('positionAmt', '0')) != 0]

    def algos(self, symbol=SYMBOL):
        return self.signed('GET', '/fapi/v1/openAlgoOrders', {'symbol': symbol})

    def cancel_algos(self, symbol=SYMBOL):
        for order in self.algos(symbol):
            self.signed('DELETE', '/fapi/v1/algoOrder', {'algoId': order['algoId']})
            emit('protection_cancelled', symbol=symbol, algo_id=order['algoId'])

    def close(self, state, reason, symbol=None):
        symbol = symbol or state.get('entry_symbol') or SYMBOL
        position = self.position(symbol)
        amount = Decimal(position['positionAmt'])
        if amount == 0:
            self.cancel_algos(symbol)
            return
        self.cancel_algos(symbol)
        side = 'SELL' if amount > 0 else 'BUY'
        client_id = 'at_local_exit_' + str(int(time.time() * 1000))
        result = self.signed('POST', '/fapi/v1/order', {
            'symbol': symbol, 'side': side, 'type': 'MARKET',
            'quantity': str(abs(amount)), 'reduceOnly': 'true',
            'newClientOrderId': client_id, 'newOrderRespType': 'RESULT'})
        if Decimal(self.position(symbol)['positionAmt']) != 0:
            raise RuntimeError('position remained after close')
        self.record_close(state, reason, result['orderId'], symbol)

    def position_pnl(self, state, close_order_id=None, symbol=None):
        symbol = symbol or state.get('entry_symbol') or SYMBOL
        start_ms = max(0, int(state.get('entry_time') or time.time()) * 1000 - 60_000)
        trades = []
        for attempt in range(6):
            trades = self.signed('GET', '/fapi/v1/userTrades', {
                'symbol': symbol, 'startTime': start_ms, 'limit': 1000})
            if close_order_id is None or any(
                    int(item['orderId']) == int(close_order_id) for item in trades):
                break
            time.sleep(0.25 * (attempt + 1))
        realized = sum((Decimal(item['realizedPnl']) for item in trades), Decimal())
        fees = sum((Decimal(item['commission']) for item in trades
                    if item['commissionAsset'] == 'USDT'), Decimal())
        funding_rows = self.signed('GET', '/fapi/v1/income', {
            'symbol': symbol, 'incomeType': 'FUNDING_FEE',
            'startTime': start_ms, 'limit': 1000})
        funding = sum((Decimal(item['income']) for item in funding_rows
                       if item.get('asset') == 'USDT'), Decimal())
        return realized - fees + funding

    def record_close(self, state, reason, order_id=None, symbol=None):
        symbol = symbol or state.get('entry_symbol') or SYMBOL
        pnl = self.position_pnl(state, order_id, symbol)
        now_ts = int(time.time())
        state['consecutive_losses'] = state.get('consecutive_losses', 0) + 1 if pnl < 0 else 0
        state['last_loss_time'] = now_ts if pnl < 0 else None
        state.update(entry_time=None, entry_symbol=None, entry_side=None,
                     entry_order=None, entry_price=None,
                     strategy_exit_lookback=None, last_close_order=order_id,
                     last_close_time=now_ts)
        save_state(state)
        emit('position_closed', symbol=symbol, reason=reason, order_id=order_id,
             net_pnl=str(pnl),
             consecutive_losses=state['consecutive_losses'])

    def daily_net(self):
        start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0,
                                                   microsecond=0)
        income = self.signed('GET', '/fapi/v1/income', {
            'startTime': int(start.timestamp() * 1000), 'limit': 1000})
        return sum((Decimal(item['income']) for item in income
                    if item.get('asset') == 'USDT'), Decimal())

    def candles(self, symbol, interval, limit=61):
        return self.public('/fapi/v1/klines', {'symbol': symbol, 'interval': interval,
                                               'limit': limit})[:-1]

    def strategy(self, symbol=SYMBOL, exit_lookback=None):
        return breakout_signal(self.candles(symbol, '1h'), self.candles(symbol, '4h'),
                               exit_lookback=exit_lookback)

    def macro_entry_permissions(self):
        limit = max(BTC_DAILY_EMA_PERIOD * 3 + 1, BTC_DAILY_EMA_PERIOD + 2)
        daily = self.candles('BTCUSDT', '1d', limit=limit)
        if len(daily) < BTC_DAILY_EMA_PERIOD:
            raise RuntimeError('insufficient BTC daily candles')
        closes = [Decimal(row[4]) for row in daily]
        daily_ema = ema(closes, BTC_DAILY_EMA_PERIOD)
        close = closes[-1]
        return {
            'btc_close': close,
            'btc_daily_ema': daily_ema,
            'allow_long': close > daily_ema,
            'allow_short': ALLOW_SHORT and close < daily_ema,
        }

    def symbol_info(self, symbol):
        if self._exchange_info is None:
            self._exchange_info = self.public('/fapi/v1/exchangeInfo')
        return next(x for x in self._exchange_info['symbols'] if x['symbol'] == symbol)

    def quantity_for(self, symbol, reference_price):
        info = self.symbol_info(symbol)
        filters = {item['filterType']: item for item in info['filters']}
        lot = filters.get('MARKET_LOT_SIZE') or filters['LOT_SIZE']
        step = Decimal(lot['stepSize'])
        minimum = Decimal(lot['minQty'])
        quantity = (TARGET_NOTIONAL / Decimal(reference_price) / step).to_integral_value(
            rounding=ROUND_DOWN) * step
        if quantity < minimum:
            raise RuntimeError(f'{symbol} target notional is below minimum quantity')
        return quantity

    def protect(self, symbol, side, entry):
        info = self.symbol_info(symbol)
        tick = Decimal(next(x['tickSize'] for x in info['filters']
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
                    'algoType': 'CONDITIONAL', 'symbol': symbol, 'side': close_side,
                    'positionSide': 'BOTH', 'type': order_type,
                    'triggerPrice': str(trigger), 'closePosition': 'true',
                    'workingType': 'MARK_PRICE', 'priceProtect': 'false',
                    'clientAlgoId': 'at_local_' + label + '_' + str(int(time.time() * 1000))})
                created.append(result['algoId'])
            active = {x['algoId'] for x in self.algos(symbol)}
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

    def enter(self, state, symbol, side, reference_price):
        quantity = self.quantity_for(symbol, reference_price)
        self.signed('POST', '/fapi/v1/leverage', {'symbol': symbol, 'leverage': 1})
        try:
            self.signed('POST', '/fapi/v1/marginType', {'symbol': symbol,
                                                        'marginType': 'ISOLATED'})
        except httpx.HTTPStatusError as exc:
            if exc.response.json().get('code') != -4046:
                raise
        order_side = 'BUY' if side == 'LONG' else 'SELL'
        result = self.signed('POST', '/fapi/v1/order', {
            'symbol': symbol, 'side': order_side, 'type': 'MARKET',
            'quantity': str(quantity), 'newOrderRespType': 'RESULT',
            'newClientOrderId': 'at_local_entry_' + str(int(time.time() * 1000))})
        position = self.position(symbol)
        state.update(entry_time=int(time.time()), entry_symbol=symbol, entry_side=side,
                     entry_order=result['orderId'], entry_price=position['entryPrice'],
                     strategy_exit_lookback=EXIT_LOOKBACK)
        save_state(state)
        try:
            stop = self.protect(symbol, side, Decimal(position['entryPrice']))
        except Exception:
            self.close(state, 'protection_failed', symbol)
            raise
        emit('position_opened', symbol=symbol, side=side, quantity=str(quantity),
             order_id=result['orderId'], entry=position['entryPrice'], stop=str(stop))


def cycle(api, state):
    positions = api.positions()
    if len(positions) > 1:
        raise RuntimeError('multiple futures positions detected; refusing automatic changes')
    position = positions[0] if positions else None
    symbol = position['symbol'] if position else None
    amount = Decimal(position['positionAmt']) if position else Decimal(0)
    managed_position = position if symbol in SYMBOLS else None
    managed_algos = {item: api.algos(item) for item in SYMBOLS}
    control = load_runtime_state()
    if control.kill_switch:
        if managed_position is not None:
            api.close(state, 'kill_switch', symbol)
        else:
            for item, orders in managed_algos.items():
                if orders:
                    api.cancel_algos(item)
        return
    if position is not None and managed_position is None:
        emit('entry_blocked', reason='unmanaged_futures_position', symbol=symbol)
        return
    if managed_position is not None:
        algos = managed_algos[symbol]
        for item, orders in managed_algos.items():
            if item != symbol and orders:
                api.cancel_algos(item)
        active_exit_lookback = int(state.get('strategy_exit_lookback') or
                                   ACTIVE_POSITION_EXIT_LOOKBACK)
        if not state.get('strategy_exit_lookback'):
            state['strategy_exit_lookback'] = active_exit_lookback
            save_state(state)
        strategy = api.strategy(symbol, exit_lookback=active_exit_lookback)
        expected_side = 'LONG' if amount > 0 else 'SHORT'
        if len(algos) != 1 or {x.get('orderType') for x in algos} != {'STOP_MARKET'}:
            api.close(state, 'protection_missing', symbol)
            return
        if not state.get('entry_time'):
            state.update(entry_time=int(time.time()), entry_symbol=symbol,
                         entry_side=expected_side)
            save_state(state)
        elif state.get('entry_symbol') != symbol:
            state['entry_symbol'] = symbol
            save_state(state)
        should_exit = (expected_side == 'LONG' and strategy['exit_long']) or (
            expected_side == 'SHORT' and strategy['exit_short'])
        if should_exit:
            api.close(state, 'channel_exit', symbol)
        return
    for item, orders in managed_algos.items():
        if orders:
            api.cancel_algos(item)
    if state.get('entry_time'):
        api.record_close(state, 'exchange_protection',
                         symbol=state.get('entry_symbol') or SYMBOL)
    if control.paused:
        return
    macro = api.macro_entry_permissions()
    emit('macro_filter', btc_close=str(macro['btc_close']),
         btc_daily_ema=str(macro['btc_daily_ema']),
         allow_long=macro['allow_long'], allow_short=macro['allow_short'])
    last_candles = state.setdefault('last_candles', {})
    candidates = []
    for item in SYMBOLS:
        try:
            strategy = api.strategy(item)
        except Exception as exc:
            emit('symbol_scan_failed', symbol=item, error=type(exc).__name__,
                 detail=str(exc)[:200])
            continue
        if last_candles.get(item) == strategy['candle']:
            continue
        last_candles[item] = strategy['candle']
        if item == SYMBOL:
            state['last_candle'] = strategy['candle']
        emit('strategy_evaluated', symbol=item, candle=strategy['candle'],
             close=str(strategy['close']), regime=strategy['regime'],
             regime_spread=str(strategy['regime_spread']), entry=strategy['entry'])
        entry_allowed = (
            strategy['entry'] == 'LONG' and macro['allow_long'] or
            strategy['entry'] == 'SHORT' and macro['allow_short'])
        if strategy['entry'] and entry_allowed:
            candidates.append((strategy['entry_strength'], item, strategy))
    save_state(state)
    daily_net = api.daily_net()
    if daily_net <= -DAILY_LOSS_LIMIT or loss_streak_blocked(state):
        return
    if state.get('last_close_time') and (
            time.time() - state['last_close_time'] < ENTRY_COOLDOWN_SECONDS):
        return
    if candidates:
        projected_net = daily_net - estimated_worst_case_loss()
        if projected_net <= -DAILY_LOSS_LIMIT:
            emit('entry_blocked', reason='daily_loss_budget',
                 daily_net=str(daily_net), projected_net=str(projected_net),
                 daily_loss_limit=str(DAILY_LOSS_LIMIT))
            return
        _, selected_symbol, selected = max(candidates, key=lambda item: item[0])
        api.enter(state, selected_symbol, selected['entry'], selected['close'])


def run():
    import fcntl
    DATA.mkdir(parents=True, exist_ok=True)
    with (DATA / 'binance_live.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        api = Binance()
        state = load_state()
        emit('worker_started', symbols=list(SYMBOLS),
             target_notional_usdt=str(TARGET_NOTIONAL), stop_rate=str(STOP_RATE),
             exit_lookback=EXIT_LOOKBACK,
             min_regime_spread_rate=str(MIN_REGIME_SPREAD_RATE),
             allow_short=ALLOW_SHORT, btc_daily_ema_period=BTC_DAILY_EMA_PERIOD)
        while True:
            try:
                cycle(api, state)
            except Exception as exc:
                if isinstance(exc, httpx.HTTPStatusError):
                    detail = (f'status={exc.response.status_code} '
                              f'path={exc.request.url.path} body={exc.response.text[:200]}')
                else:
                    detail = str(exc)[:300]
                emit('cycle_failed', error=type(exc).__name__, detail=detail)
            if os.environ.get('BINANCE_LIVE_ONCE') == 'true':
                return
            time.sleep(60)


if __name__ == '__main__':
    run()

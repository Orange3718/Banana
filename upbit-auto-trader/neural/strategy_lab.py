"""Offline strategy research. It cannot place orders or read credentials."""
from dataclasses import dataclass, asdict
from math import sqrt
from random import Random


@dataclass(frozen=True)
class Candle:
    time: str
    open: float
    high: float
    low: float
    close: float
    volume: float


CATALOG = [
    {'id': 'donchian', 'name': 'Donchian 추세 돌파', 'market': '현물·선물',
     'entry': '최근 20봉 최고가 돌파 + 거래량 확인', 'exit': '최근 10봉 최저가 이탈',
     'risk': '횡보장에서 잦은 손절', 'status': 'offline_ready'},
    {'id': 'dual_thrust', 'name': 'Dual Thrust 변동성 돌파', 'market': '현물·선물',
     'entry': '이전 변동범위로 계산한 상단선 돌파', 'exit': '하단선 이탈',
     'risk': '급등 직후 추격 진입', 'status': 'offline_ready'},
    {'id': 'rsi_bollinger', 'name': 'RSI2·볼린저 평균회귀', 'market': '현물 우선',
     'entry': '장기 추세 위에서 단기 과매도·하단밴드 접근', 'exit': '중앙선 회복',
     'risk': '하락 추세에서 계속 저가 갱신', 'status': 'offline_ready'},
]


def sma(values, window):
    return None if len(values) < window else sum(values[-window:]) / window


def rsi(values, window=2):
    if len(values) <= window:
        return None
    changes = [values[i] - values[i - 1] for i in range(len(values) - window, len(values))]
    gains = sum(max(x, 0) for x in changes) / window
    losses = sum(max(-x, 0) for x in changes) / window
    if losses == 0:
        return 100.0
    return 100 - 100 / (1 + gains / losses)


def bands(values, window=20, deviations=2):
    mid = sma(values, window)
    if mid is None:
        return None
    sample = values[-window:]
    std = sqrt(sum((x - mid) ** 2 for x in sample) / window)
    return mid - deviations * std, mid, mid + deviations * std


def regime(candles, index):
    closes = [c.close for c in candles[:index + 1]]
    fast, slow = sma(closes, 20), sma(closes, 60)
    if slow is None:
        return 'warmup'
    recent = candles[max(1, index - 13):index + 1]
    atr = sum(max(c.high - c.low, abs(c.high - candles[index - 1].close),
                  abs(c.low - candles[index - 1].close)) for c in recent) / len(recent)
    if atr / candles[index].close > 0.045:
        return 'risk'
    if fast > slow * 1.005:
        return 'bullish'
    if fast < slow * .995:
        return 'bearish'
    return 'range'


def signal(strategy, candles, index, in_position):
    if index < 60:
        return 'HOLD', '지표 준비 구간'
    current = candles[index]
    state = regime(candles, index)
    if state == 'risk':
        return ('SELL', '고변동성 보호 청산') if in_position else ('HOLD', '고변동성 신규 진입 중지')
    closes = [c.close for c in candles[:index + 1]]
    if strategy == 'donchian':
        upper = max(c.high for c in candles[index - 20:index])
        lower = min(c.low for c in candles[index - 10:index])
        avg_volume = sum(c.volume for c in candles[index - 20:index]) / 20
        if not in_position and state == 'bullish' and current.close > upper and current.volume >= avg_volume:
            return 'BUY', '20봉 최고가와 평균 거래량 동시 돌파'
        if in_position and current.close < lower:
            return 'SELL', '10봉 최저가 이탈'
    elif strategy == 'dual_thrust':
        prior = candles[index - 20:index]
        width = max(max(c.high for c in prior) - min(c.close for c in prior),
                    max(c.close for c in prior) - min(c.low for c in prior))
        if not in_position and state in {'bullish', 'range'} and current.close > current.open + .5 * width:
            return 'BUY', '변동범위 상단 돌파'
        if in_position and current.close < current.open - .5 * width:
            return 'SELL', '변동범위 하단 이탈'
    elif strategy == 'rsi_bollinger':
        channel = bands(closes)
        value = rsi(closes)
        if channel:
            low, mid, _ = channel
            if not in_position and state in {'bullish', 'range'} and value is not None and value <= 15 and current.close <= low * 1.005:
                return 'BUY', 'RSI2 과매도와 볼린저 하단 확인'
            if in_position and (current.close >= mid or (value is not None and value >= 70)):
                return 'SELL', '평균선 회복 또는 RSI 정상화'
    return 'HOLD', f'{state} 구간 진입 조건 미충족'


def backtest(candles, strategy, fee_rate=.0005, slippage_rate=.0005,
             stop_loss=.025, take_profit=.045, initial=1_000_000):
    if strategy not in {x['id'] for x in CATALOG}:
        raise ValueError('unknown strategy')
    cash, quantity, entry = float(initial), 0.0, 0.0
    trades, curve = [], []
    pending = None
    for index, candle in enumerate(candles):
        if pending == 'BUY' and quantity == 0:
            price = candle.open * (1 + slippage_rate)
            quantity = cash * (1 - fee_rate) / price
            cash, entry = 0.0, price
        elif pending == 'SELL' and quantity > 0:
            price = candle.open * (1 - slippage_rate)
            proceeds = quantity * price * (1 - fee_rate)
            trades.append((proceeds / (quantity * entry) - 1) * 100)
            cash, quantity, entry = proceeds, 0.0, 0.0
        pending = None
        if quantity > 0 and (candle.close <= entry * (1 - stop_loss) or candle.close >= entry * (1 + take_profit)):
            pending = 'SELL'
        else:
            action, _ = signal(strategy, candles, index, quantity > 0)
            if action == 'BUY' and quantity == 0:
                pending = 'BUY'
            elif action == 'SELL' and quantity > 0:
                pending = 'SELL'
        curve.append(cash + quantity * candle.close)
    if quantity > 0:
        proceeds = quantity * candles[-1].close * (1 - fee_rate - slippage_rate)
        trades.append((proceeds / (quantity * entry) - 1) * 100)
        cash = proceeds
    peak, drawdown = curve[0] if curve else initial, 0.0
    for value in curve:
        peak = max(peak, value)
        drawdown = min(drawdown, value / peak - 1)
    wins = [x for x in trades if x > 0]
    losses = [x for x in trades if x <= 0]
    gross_win, gross_loss = sum(wins), abs(sum(losses))
    return {'strategy': strategy, 'trades': len(trades),
            'win_rate_pct': round(len(wins) / len(trades) * 100, 2) if trades else 0,
            'net_return_pct': round((cash / initial - 1) * 100, 2),
            'max_drawdown_pct': round(drawdown * 100, 2),
            'profit_factor': round(gross_win / gross_loss, 2) if gross_loss else None,
            'fee_rate_pct': fee_rate * 100, 'slippage_rate_pct': slippage_rate * 100,
            'research_only': True}


def sample_candles(count=360, seed=17):
    random = Random(seed)
    price, rows = 100.0, []
    for i in range(count):
        drift = .001 if (i // 90) % 2 == 0 else -.0002
        change = drift + random.gauss(0, .008)
        open_price = price
        price = max(1, price * (1 + change))
        spread = abs(random.gauss(.006, .003))
        rows.append(Candle(str(i), open_price, max(open_price, price) * (1 + spread),
                           min(open_price, price) * (1 - spread), price,
                           1000 * (1 + abs(change) * 20 + random.random())))
    return rows


def demo_reports():
    candles = sample_candles()
    return {'dataset': '고정 시드 합성 캔들 · 실거래 성과 아님',
            'reports': [backtest(candles, item['id']) for item in CATALOG],
            'catalog': CATALOG}

from decimal import Decimal

import httpx


def candle(close, high=None, low=None, close_time=0):
    high = close + 1 if high is None else high
    low = close - 1 if low is None else low
    return [0, str(close), str(high), str(low), str(close), '1', close_time]


def test_breakout_requires_hourly_breakout_in_four_hour_regime():
    from neural.binance_live import breakout_signal

    hourly = [candle(100 + i, close_time=i) for i in range(30)]
    hourly[-1] = candle(140, high=141, low=139, close_time=999)
    four_hour = [candle(100 + i, close_time=i) for i in range(60)]

    result = breakout_signal(hourly, four_hour)

    assert result['regime'] == 'LONG'
    assert result['entry'] == 'LONG'
    assert result['candle'] == 999


def test_breakout_can_open_short_only_in_short_regime():
    from neural.binance_live import breakout_signal

    hourly = [candle(200 - i, close_time=i) for i in range(30)]
    hourly[-1] = candle(150, high=151, low=149, close_time=1000)
    four_hour = [candle(200 - i, close_time=i) for i in range(60)]

    result = breakout_signal(hourly, four_hour)

    assert result['regime'] == 'SHORT'
    assert result['entry'] == 'SHORT'


def test_breakout_direction_permissions_block_disallowed_side():
    from neural.binance_live import breakout_signal

    hourly = [candle(200 - i, close_time=i) for i in range(30)]
    hourly[-1] = candle(150, high=151, low=149, close_time=1000)
    four_hour = [candle(200 - i, close_time=i) for i in range(60)]

    result = breakout_signal(hourly, four_hour, allow_short=False)

    assert result['regime'] == 'SHORT'
    assert result['entry'] is None


def test_breakout_confirmation_requires_move_beyond_high(monkeypatch):
    from neural import binance_live

    monkeypatch.setattr(binance_live, 'ENTRY_CONFIRMATION_RATE', Decimal('0.0025'))
    hourly = [candle(100 + i, close_time=i) for i in range(30)]
    four_hour = [candle(100 + i, close_time=i) for i in range(60)]

    hourly[-1] = candle(129.2, high=129.3, low=128.0, close_time=1001)
    result = binance_live.breakout_signal(hourly, four_hour)
    assert result['entry'] is None

    hourly[-1] = candle(129.4, high=129.5, low=128.0, close_time=1002)
    result = binance_live.breakout_signal(hourly, four_hour)
    assert result['entry'] == 'LONG'


def test_breakout_skips_weak_four_hour_regime(monkeypatch):
    from neural import binance_live

    monkeypatch.setattr(binance_live, 'MIN_REGIME_SPREAD_RATE', Decimal('0.001'))
    hourly = [candle(100 + i, close_time=i) for i in range(30)]
    hourly[-1] = candle(140, high=141, low=139, close_time=1003)
    four_hour = [candle(100 + Decimal(i) / 1000, close_time=i) for i in range(60)]

    result = binance_live.breakout_signal(hourly, four_hour)

    assert result['entry'] is None
    assert result['regime_spread'] < Decimal('0.001')


def test_open_position_keeps_legacy_exit_lookback(monkeypatch):
    from types import SimpleNamespace
    from neural import binance_live

    class Api:
        def __init__(self):
            self.exit_lookback = None

        def positions(self):
            return [{'symbol': 'BTCUSDT', 'positionAmt': '0.005'}]

        def algos(self, _symbol):
            return [{'orderType': 'STOP_MARKET'}]

        def strategy(self, _symbol, exit_lookback=None):
            self.exit_lookback = exit_lookback
            return {'exit_long': False, 'exit_short': False}

    api = Api()
    state = {'entry_time': 1, 'entry_side': 'LONG'}
    monkeypatch.setattr(binance_live, 'SYMBOLS', ('BTCUSDT',))
    monkeypatch.setattr(binance_live, 'ACTIVE_POSITION_EXIT_LOOKBACK', 4)
    monkeypatch.setattr(binance_live, 'load_runtime_state',
                        lambda: SimpleNamespace(kill_switch=False, paused=False))
    monkeypatch.setattr(binance_live, 'save_state', lambda _state: None)

    binance_live.cycle(api, state)

    assert api.exit_lookback == 4
    assert state['strategy_exit_lookback'] == 4


def test_position_pnl_includes_entry_and_exit_fees():
    from neural.binance_live import Binance

    api = object.__new__(Binance)
    def signed(_method, path, _params):
        if path == '/fapi/v1/income':
            return [{'income': '-0.02', 'asset': 'USDT'}]
        return [
            {'orderId': 1, 'realizedPnl': '0', 'commission': '0.04',
             'commissionAsset': 'USDT'},
            {'orderId': 2, 'realizedPnl': '1.00', 'commission': '0.04',
             'commissionAsset': 'USDT'},
        ]
    api.signed = signed

    assert api.position_pnl({'entry_time': 100}, close_order_id=2) == Decimal('0.90')


def test_daily_net_uses_income_ledger_including_funding():
    from neural.binance_live import Binance

    api = object.__new__(Binance)
    api.signed = lambda *_args, **_kwargs: [
        {'income': '1.00', 'asset': 'USDT', 'incomeType': 'REALIZED_PNL'},
        {'income': '-0.08', 'asset': 'USDT', 'incomeType': 'COMMISSION'},
        {'income': '-0.02', 'asset': 'USDT', 'incomeType': 'FUNDING_FEE'},
    ]

    assert api.daily_net() == Decimal('0.90')


def test_worst_case_loss_includes_stop_fees_and_slippage(monkeypatch):
    from neural import binance_live

    monkeypatch.setattr(binance_live, 'TARGET_NOTIONAL', Decimal('425'))
    monkeypatch.setattr(binance_live, 'STOP_RATE', Decimal('0.025'))
    monkeypatch.setattr(binance_live, 'TAKER_FEE_RATE', Decimal('0.0005'))
    monkeypatch.setattr(binance_live, 'RISK_SLIPPAGE_RATE', Decimal('0.0002'))

    assert binance_live.estimated_worst_case_loss() == Decimal('11.2200')


def test_macro_filter_allows_long_only_above_btc_daily_ema(monkeypatch):
    from neural import binance_live

    api = object.__new__(binance_live.Binance)
    api.candles = lambda *_args, **_kwargs: [
        candle(100 + i, close_time=i) for i in range(300)
    ]
    monkeypatch.setattr(binance_live, 'BTC_DAILY_EMA_PERIOD', 100)
    monkeypatch.setattr(binance_live, 'ALLOW_SHORT', False)

    permissions = api.macro_entry_permissions()

    assert permissions['allow_long'] is True
    assert permissions['allow_short'] is False


def test_signed_resynchronizes_and_retries_timestamp_error(monkeypatch):
    from neural import binance_live

    api = object.__new__(binance_live.Binance)
    api.key = 'key'
    api.secret = b'secret'
    api.delta = 2000
    api.last_time_sync = 1.0
    sync_calls = []
    responses = [
        httpx.Response(400, json={'code': -1021, 'msg': 'timestamp outside recvWindow'},
                       request=httpx.Request('GET', 'https://example.test/fapi/v3/positionRisk')),
        httpx.Response(200, json=[{'symbol': 'BTCUSDT'}],
                       request=httpx.Request('GET', 'https://example.test/fapi/v3/positionRisk')),
    ]

    class Client:
        def request(self, *_args, **_kwargs):
            return responses.pop(0)

    api.client = Client()
    api.sync_time = lambda: (sync_calls.append(True), setattr(api, 'delta', 0),
                             setattr(api, 'last_time_sync', 2.0))
    monkeypatch.setattr(binance_live.time, 'monotonic', lambda: 1.0)
    monkeypatch.setattr(binance_live.time, 'time', lambda: 100.0)

    result = api.signed('GET', '/fapi/v3/positionRisk', {'symbol': 'BTCUSDT'})

    assert result == [{'symbol': 'BTCUSDT'}]
    assert len(sync_calls) == 1


def test_position_uses_v3_endpoint():
    from neural.binance_live import Binance

    api = object.__new__(Binance)
    calls = []
    api.signed = lambda method, path, params: (
        calls.append((method, path, params)) or
        [{'symbol': 'BTCUSDT', 'positionSide': 'BOTH', 'positionAmt': '0.005'}]
    )

    assert api.position()['positionAmt'] == '0.005'
    assert calls == [('GET', '/fapi/v3/positionRisk', {'symbol': 'BTCUSDT'})]


def test_position_treats_missing_v3_symbol_as_flat():
    from neural.binance_live import Binance

    api = object.__new__(Binance)
    api.signed = lambda *_args, **_kwargs: []

    position = api.position()

    assert position['symbol'] == 'BTCUSDT'
    assert position['positionSide'] == 'BOTH'
    assert position['positionAmt'] == '0'


def test_quantity_for_uses_equal_notional_and_symbol_step(monkeypatch):
    from neural import binance_live

    api = object.__new__(binance_live.Binance)
    api.symbol_info = lambda _symbol: {
        'filters': [
            {'filterType': 'MARKET_LOT_SIZE', 'stepSize': '0.01', 'minQty': '0.01'},
        ]
    }
    monkeypatch.setattr(binance_live, 'TARGET_NOTIONAL', Decimal('400'))

    assert api.quantity_for('ETHUSDT', Decimal('2683.41')) == Decimal('0.14')


def test_flat_cycle_selects_strongest_breakout_across_symbols(monkeypatch):
    from types import SimpleNamespace
    from neural import binance_live

    decisions = {
        'BTCUSDT': {'candle': 1, 'close': Decimal('84000'), 'regime': 'LONG',
                    'regime_spread': Decimal('0.02'), 'entry': None,
                    'entry_strength': Decimal('0'), 'exit_long': False,
                    'exit_short': False},
        'ETHUSDT': {'candle': 1, 'close': Decimal('2700'), 'regime': 'LONG',
                    'regime_spread': Decimal('0.02'), 'entry': 'LONG',
                    'entry_strength': Decimal('0.003'), 'exit_long': False,
                    'exit_short': False},
        'SOLUSDT': {'candle': 1, 'close': Decimal('115'), 'regime': 'LONG',
                    'regime_spread': Decimal('0.03'), 'entry': 'LONG',
                    'entry_strength': Decimal('0.006'), 'exit_long': False,
                    'exit_short': False},
    }

    class Api:
        def __init__(self):
            self.entered = None

        def positions(self):
            return []

        def algos(self, _symbol):
            return []

        def strategy(self, symbol):
            return decisions[symbol]

        def daily_net(self):
            return Decimal('0')

        def macro_entry_permissions(self):
            return {'btc_close': Decimal('90000'), 'btc_daily_ema': Decimal('85000'),
                    'allow_long': True, 'allow_short': False}

        def enter(self, state, symbol, side, close):
            self.entered = (symbol, side, close)

    api = Api()
    state = {'entry_time': None, 'last_close_time': None, 'consecutive_losses': 0,
             'last_candles': {}}
    monkeypatch.setattr(binance_live, 'SYMBOLS', ('BTCUSDT', 'ETHUSDT', 'SOLUSDT'))
    monkeypatch.setattr(binance_live, 'load_runtime_state',
                        lambda: SimpleNamespace(kill_switch=False, paused=False))
    monkeypatch.setattr(binance_live, 'save_state', lambda _state: None)

    binance_live.cycle(api, state)

    assert api.entered == ('SOLUSDT', 'LONG', Decimal('115'))


def test_flat_cycle_blocks_entry_that_can_exceed_daily_loss_budget(monkeypatch):
    from types import SimpleNamespace
    from neural import binance_live

    decision = {'candle': 1, 'close': Decimal('115'), 'regime': 'LONG',
                'regime_spread': Decimal('0.03'), 'entry': 'LONG',
                'entry_strength': Decimal('0.006'), 'exit_long': False,
                'exit_short': False}

    class Api:
        entered = False

        def positions(self):
            return []

        def algos(self, _symbol):
            return []

        def macro_entry_permissions(self):
            return {'btc_close': Decimal('90000'), 'btc_daily_ema': Decimal('85000'),
                    'allow_long': True, 'allow_short': False}

        def strategy(self, _symbol):
            return decision

        def daily_net(self):
            return Decimal('-5')

        def enter(self, *_args):
            self.entered = True

    api = Api()
    state = {'entry_time': None, 'last_close_time': None, 'consecutive_losses': 0,
             'last_candles': {}}
    monkeypatch.setattr(binance_live, 'SYMBOLS', ('SOLUSDT',))
    monkeypatch.setattr(binance_live, 'TARGET_NOTIONAL', Decimal('425'))
    monkeypatch.setattr(binance_live, 'STOP_RATE', Decimal('0.025'))
    monkeypatch.setattr(binance_live, 'DAILY_LOSS_LIMIT', Decimal('15'))
    monkeypatch.setattr(binance_live, 'load_runtime_state',
                        lambda: SimpleNamespace(kill_switch=False, paused=False))
    monkeypatch.setattr(binance_live, 'save_state', lambda _state: None)

    binance_live.cycle(api, state)

    assert api.entered is False

from decimal import Decimal


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


def test_position_pnl_includes_entry_and_exit_fees():
    from neural.binance_live import Binance

    api = object.__new__(Binance)
    api.signed = lambda *_args, **_kwargs: [
        {'orderId': 1, 'realizedPnl': '0', 'commission': '0.04',
         'commissionAsset': 'USDT'},
        {'orderId': 2, 'realizedPnl': '1.00', 'commission': '0.04',
         'commissionAsset': 'USDT'},
    ]

    assert api.position_pnl({'entry_time': 100}, close_order_id=2) == Decimal('0.92')

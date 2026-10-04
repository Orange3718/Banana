import json
from decimal import Decimal

from neural.upbit_ledger import paid_fees, reconstruct, summarize
from settings_store import load_settings


def _row(time, kind, uuid, price, volume, fee, *, rate=None, strategy='trend_confirmation'):
    return {
        'time': time, 'event': kind, 'market': 'KRW-BTC', 'execution_status': 'filled',
        'profit_rate': rate, 'recommendation': {'strategy_name': strategy},
        'final_result': {
            'uuid': uuid, 'paid_fee': str(fee),
            'trades': [{'volume': str(volume), 'funds': str(price * volume)}],
        },
    }


def test_fifo_uses_fills_and_both_fees_even_when_display_rate_is_positive(tmp_path):
    history = tmp_path / 'history.jsonl'
    rows = [
        _row('2026-10-02 01:00:00', 'auto_buy', 'a', 100, 1, 0.05),
        _row('2026-10-02 02:00:00', 'auto_buy', 'b', 80, 1, 0.04),
        _row('2026-10-03 01:00:00', 'auto_sell', 'c', 90, 1, 0.045, rate=0.001),
    ]
    history.write_text('\n'.join(json.dumps(row) for row in rows) + '\n')
    exits, fees = reconstruct(history)
    result = summarize(exits, '2026-10-02', '2026-10-05')
    assert result['realized_net_krw'] == '-10.095'
    assert result['closed_orders'] == 1
    assert result['win_rate'] == '0'
    assert paid_fees(fees, '2026-10-02', '2026-10-05') == '0.135'
    assert paid_fees(fees, '2026-10-03', '2026-10-04') == '0.045'


def test_unknown_opening_inventory_is_not_assigned_a_fictitious_cost(tmp_path):
    history = tmp_path / 'history.jsonl'
    history.write_text(json.dumps(_row('2026-10-03 01:00:00', 'auto_sell', 'c', 90, 1, 0.045)) + '\n')
    exits, _ = reconstruct(history)
    result = summarize(exits, '2026-10-02', '2026-10-05')
    assert result['unmatched_orders'] == 1
    assert result['realized_net_krw'] is None


def test_partial_exit_splits_net_by_actual_entry_strategy(tmp_path):
    history = tmp_path / 'history.jsonl'
    rows = [
        _row('2026-10-02 01:00:00', 'auto_buy', 'a', 100, Decimal('0.5'),
             Decimal('0.025'), strategy='trend_confirmation'),
        _row('2026-10-02 02:00:00', 'auto_buy', 'b', 80, Decimal('0.5'),
             Decimal('0.020'), strategy='trend_pullback'),
        _row('2026-10-03 01:00:00', 'auto_sell', 'c', 90, Decimal('0.75'),
             Decimal('0.03375')),
    ]
    history.write_text('\n'.join(json.dumps(row) for row in rows) + '\n')
    exits, _ = reconstruct(history)
    result = summarize(exits, '2026-10-02', '2026-10-05')
    assert result['realized_net_krw'] == '-2.56875'
    assert result['by_entry_strategy_krw'] == {
        'trend_confirmation': '-5.0475',
        'trend_pullback': '2.47875',
    }


def test_recreated_settings_keep_unvalidated_entries_off(tmp_path):
    settings = load_settings(tmp_path / 'missing-settings.json')
    assert settings.enable_trend_confirmation is True
    assert settings.enable_trend_pullback is False
    assert settings.enable_volatility_breakout is False
    assert settings.enable_mean_reversion is False

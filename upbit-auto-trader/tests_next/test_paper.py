from types import SimpleNamespace
from neural import paper, strategy_lab
from risk_manager import RiskManager


def test_loss_gate_allows_exit():
    risk = RiskManager(SimpleNamespace(max_daily_loss=.05, min_order_krw=1))
    risk.daily_start_equity = 100
    position = SimpleNamespace(has_position=True, volume=1)
    assert risk.validate({'action':'SELL', 'sell_ratio':1}, position, 0, 90, 90).allowed
    assert not risk.validate({'action':'BUY'}, position, 0, 90, 90).allowed


def test_paper_dedup_and_restart(tmp_path, monkeypatch):
    rows = strategy_lab.sample_candles(70)
    monkeypatch.setattr(paper, 'signal', lambda *a: ('BUY', 'test'))
    state = paper.advance(None, rows[:-1], 100, 'donchian', 'upbit')
    state = paper.advance(state, rows, 100, 'donchian', 'upbit')
    quantity = state['quantity']
    assert quantity > 0
    db = paper.connect(tmp_path / 'test.db')
    with db:
        db.execute('INSERT INTO portfolios VALUES (?,?)', ('test', paper.json.dumps(state)))
    db.close()
    db = paper.connect(tmp_path / 'test.db')
    restored = paper.json.loads(db.execute('SELECT payload FROM portfolios').fetchone()[0])
    assert paper.advance(restored, rows, 100, 'donchian', 'upbit')['quantity'] == quantity
    db.close()


def test_round_trip_costs(monkeypatch):
    rows = [strategy_lab.Candle(str(i),100,100,100,100,100) for i in range(5)]
    monkeypatch.setattr(strategy_lab, 'signal', lambda s,c,i,p: ('SELL' if p else 'BUY', 'test'))
    result = strategy_lab.backtest(rows[:3], 'donchian', fee_rate=.01, slippage_rate=0)
    assert result['trades'] == 1
    assert result['net_return_pct'] == -1.99
    assert result['win_rate_pct'] == 0
    assert result['max_drawdown_pct'] == -1.99

from types import SimpleNamespace

import pytest

import main
from coin_registry import CoinEntry
from main import (
    _daily_loss_block_reason,
    _estimated_entry_loss_krw,
    _open_risk_block_reason,
    _suppress_legacy_market_order,
    monitor_altcoin_exits,
)
from market_scanner import scan_candidates
from settings_store import TradingSettings


class FakeClient:
    def __init__(self):
        self.requested_markets = []

    def _request(self, method, path, params):
        markets = params["markets"].split(",")
        self.requested_markets.extend(markets)
        return [
            {
                "market": market,
                "trade_price": 100.0,
                "signed_change_rate": 0.01,
                "acc_trade_price_24h": 10_000_000_000.0,
                "acc_trade_volume_24h": 1_000_000.0,
            }
            for market in markets
        ]


def test_auto_mode_scans_only_explicitly_allowed_markets():
    registry = {
        "KRW-BTC": CoinEntry(market="KRW-BTC", allow_auto_trade=True),
        "KRW-ETH": CoinEntry(market="KRW-ETH", allow_auto_trade=True),
        "KRW-DOGE": CoinEntry(market="KRW-DOGE", allow_auto_trade=False),
    }
    settings = TradingSettings(include_btc=True)
    client = FakeClient()

    candidates = scan_candidates(client, registry, settings, auto_trade_only=True)

    assert set(candidates["market"]) == {"KRW-BTC", "KRW-ETH"}
    assert set(client.requested_markets) == {"KRW-BTC", "KRW-ETH"}


def test_recommendation_mode_keeps_non_auto_candidates():
    registry = {
        "KRW-BTC": CoinEntry(market="KRW-BTC", allow_auto_trade=True),
        "KRW-DOGE": CoinEntry(market="KRW-DOGE", allow_auto_trade=False),
    }
    settings = TradingSettings(include_btc=True)

    candidates = scan_candidates(FakeClient(), registry, settings)

    assert set(candidates["market"]) == {"KRW-BTC", "KRW-DOGE"}


def test_portfolio_engine_suppresses_legacy_sell_signal():
    signal = {"action": "SELL", "sell_ratio": 1.0, "reason": "1분봉 하락"}
    settings = TradingSettings(operation_mode=4, recommendation_enabled=True)

    routed = _suppress_legacy_market_order(signal, settings)

    assert routed["action"] == "HOLD"
    assert routed["sell_ratio"] == 0.0


class ExitClient:
    def __init__(self):
        self.sold_markets = []

    def get_accounts(self):
        return [{"currency": "BTC", "balance": "0.001", "locked": "0", "avg_buy_price": "100000000"}]

    def get_current_price(self, market):
        return 110_000_000.0

    def market_sell(self, market, volume):
        self.sold_markets.append(market)
        return {"uuid": "sell-1", "state": "wait", "executed_volume": "0"}

    def get_order(self, uuid_value):
        return {"uuid": uuid_value, "state": "done", "executed_volume": "0.001", "paid_fee": "55"}


class SilentNotifier:
    def step(self, *args, **kwargs):
        return None

    def telegram(self, *args, **kwargs):
        return None


def test_portfolio_exit_manager_includes_primary_btc_market(monkeypatch):
    monkeypatch.setattr(main, "append_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(main, "update_state", lambda *args, **kwargs: None)
    monkeypatch.setattr(main.time, "sleep", lambda *args, **kwargs: None)
    client = ExitClient()
    config = SimpleNamespace(
        dry_run=False,
        real_trade_enabled=True,
        market="KRW-BTC",
        min_order_krw=5_000.0,
        take_profit_sell_ratio_1=0.5,
    )
    settings = TradingSettings(operation_mode=4, approval_required=False)
    registry = {"KRW-BTC": CoinEntry(market="KRW-BTC", allow_auto_trade=True)}

    results = monitor_altcoin_exits(
        config=config,
        client=client,
        settings=settings,
        registry=registry,
        positions={},
        notifier=SilentNotifier(),
    )

    assert client.sold_markets == ["KRW-BTC"]
    assert results[0]["market"] == "KRW-BTC"


def test_estimated_entry_loss_includes_stop_fee_and_slippage():
    settings = TradingSettings(
        stop_loss_rate=0.025,
        taker_fee_rate=0.0005,
        risk_slippage_rate=0.0005,
    )

    assert _estimated_entry_loss_krw(40_000.0, settings) == pytest.approx(1_080.0)


def test_daily_loss_gate_includes_projected_entry_loss(monkeypatch, tmp_path):
    history_path = tmp_path / "trade_history.jsonl"
    history_path.write_text(
        '{"time":"2026-09-27 09:00:00","event":"daily_equity_baseline","total_equity":500000}\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(main, "HISTORY_PATH", history_path)
    monkeypatch.setattr(main, "datetime", SimpleNamespace(now=lambda: SimpleNamespace(strftime=lambda _: "2026-09-27")))
    settings = TradingSettings(max_daily_loss_rate=0.015)

    reason = _daily_loss_block_reason(493_000.0, settings, projected_loss_krw=1_080.0)

    assert "하루 계좌 손실 제한" in reason


def test_open_risk_gate_includes_existing_positions():
    settings = TradingSettings(max_open_risk_rate=0.015)

    reason = _open_risk_block_reason(
        current_exposure_krw=220_000.0,
        order_krw=40_000.0,
        total_equity=450_000.0,
        settings=settings,
    )

    assert "총 오픈 리스크 한도 초과" in reason

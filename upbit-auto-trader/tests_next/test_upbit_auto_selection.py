from coin_registry import CoinEntry
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

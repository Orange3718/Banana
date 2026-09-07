from __future__ import annotations

from typing import Any

import pandas as pd

from coin_registry import CoinEntry, eligible_markets
from settings_store import TradingSettings
from upbit_client import UpbitClient


def get_krw_markets(client: UpbitClient) -> list[dict[str, Any]]:
    markets = client._request("GET", "/v1/market/all", {"isDetails": "false"})
    return [item for item in markets if str(item.get("market", "")).startswith("KRW-")]


def get_tickers(client: UpbitClient, markets: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index in range(0, len(markets), 80):
        batch = markets[index : index + 80]
        if not batch:
            continue
        rows.extend(client._request("GET", "/v1/ticker", {"markets": ",".join(batch)}))
    return rows


def scan_candidates(
    client: UpbitClient,
    registry: dict[str, CoinEntry],
    settings: TradingSettings,
) -> pd.DataFrame:
    markets = eligible_markets(registry, include_btc=settings.include_btc)
    if not markets:
        return pd.DataFrame()
    tickers = get_tickers(client, markets)
    rows: list[dict[str, Any]] = []
    for item in tickers:
        market = str(item.get("market", ""))
        entry = registry.get(market, CoinEntry(market=market))
        trade_value = float(item.get("acc_trade_price_24h", 0) or 0)
        change_rate = float(item.get("signed_change_rate", 0) or 0)
        if trade_value < settings.effective_min_24h_trade_value_krw():
            continue
        if abs(change_rate) > settings.effective_max_change_rate_abs():
            continue
        rows.append(
            {
                "market": market,
                "korean_name": entry.korean_name,
                "group": entry.group,
                "price": float(item.get("trade_price", 0) or 0),
                "change_rate": change_rate,
                "trade_value_24h": trade_value,
                "acc_trade_volume_24h": float(item.get("acc_trade_volume_24h", 0) or 0),
                "allow_telegram_approval": entry.allow_telegram_approval,
                "allow_auto_trade": entry.allow_auto_trade,
            }
        )
    if not rows:
        return pd.DataFrame()
    data = pd.DataFrame(rows)
    return data.sort_values("trade_value_24h", ascending=False).head(settings.scanner_market_limit).reset_index(drop=True)

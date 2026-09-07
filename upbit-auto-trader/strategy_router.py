from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from indicators import add_indicators
from settings_store import TradingSettings
from upbit_client import UpbitClient


@dataclass
class MarketRegime:
    name: str
    label: str
    reason: str
    allow_new_buys: bool
    btc_price: float
    ema200: float
    adx: float
    atr_rate: float


@dataclass
class StrategyDecision:
    matched: bool = False
    strategy_name: str = "none"
    strategy_label: str = "진입 조건 없음"
    score: float = 0.0
    position_size_ratio: float = 0.0
    trend: str = "관망"
    rsi: float = 0.0
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)


def detect_market_regime(client: UpbitClient) -> MarketRegime:
    candles = client.get_candles("KRW-BTC", "minute60", 240)
    close = candles["close"]
    ema20 = close.ewm(span=20, adjust=False).mean()
    ema60 = close.ewm(span=60, adjust=False).mean()
    ema200 = close.ewm(span=200, adjust=False).mean()
    indicators = add_indicators(candles, 5, 20, 60, 14).dropna()
    latest = indicators.iloc[-1]
    price = float(close.iloc[-1])
    ema20_value = float(ema20.iloc[-1])
    ema60_value = float(ema60.iloc[-1])
    ema200_value = float(ema200.iloc[-1])
    adx_value = float(latest["adx"])
    atr_rate = float(latest["atr"]) / price if price > 0 else 0.0

    if atr_rate >= 0.045:
        return MarketRegime(
            "risk",
            "위험장",
            f"BTC 1시간 변동성이 {atr_rate:.2%}로 높아 신규매수를 중단합니다.",
            False,
            price,
            ema200_value,
            adx_value,
            atr_rate,
        )
    if price > ema200_value and ema20_value > ema60_value and adx_value >= 18:
        return MarketRegime(
            "bullish",
            "상승장",
            "BTC가 EMA200 위에 있고 EMA20 > EMA60 상승 추세입니다.",
            True,
            price,
            ema200_value,
            adx_value,
            atr_rate,
        )
    if adx_value < 20 and abs(price / ema200_value - 1) <= 0.05:
        return MarketRegime(
            "range",
            "횡보장",
            "BTC ADX가 20 미만이고 EMA200 주변에서 움직입니다.",
            True,
            price,
            ema200_value,
            adx_value,
            atr_rate,
        )
    if price < ema200_value and ema20_value < ema60_value:
        return MarketRegime(
            "risk",
            "약세장",
            "BTC가 EMA200 아래이고 EMA20 < EMA60 하락 추세입니다.",
            False,
            price,
            ema200_value,
            adx_value,
            atr_rate,
        )
    return MarketRegime(
        "neutral",
        "중립장",
        "BTC 추세가 명확하지 않아 강한 돌파 신호만 허용합니다.",
        True,
        price,
        ema200_value,
        adx_value,
        atr_rate,
    )


def _higher_timeframe_uptrend(client: UpbitClient, market: str) -> bool:
    for interval in ("minute15", "minute60"):
        candles = client.get_candles(market, interval, 80)
        close = candles["close"]
        ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
        ema60 = float(close.ewm(span=60, adjust=False).mean().iloc[-1])
        if ema20 <= ema60 or float(close.iloc[-1]) <= ema60:
            return False
    return True


def evaluate_strategy(
    client: UpbitClient,
    market: str,
    ticker_row: pd.Series,
    settings: TradingSettings,
    regime: MarketRegime,
) -> StrategyDecision:
    if not regime.allow_new_buys:
        return StrategyDecision(risks=[regime.reason])

    candles = client.get_candles(market, "minute5", 120)
    indicators = add_indicators(candles, 5, 20, 60, 14).dropna()
    if len(indicators) < 21:
        return StrategyDecision(risks=["전략 판단에 필요한 캔들이 부족합니다."])

    latest = indicators.iloc[-1]
    previous = indicators.iloc[-2]
    close = float(latest["close"])
    rsi = float(latest["rsi"])
    volume_ratio = float(latest["volume"]) / max(float(latest["volume_ma20"]), 1e-12)
    change_rate = float(ticker_row["change_rate"])
    prior_high = float(indicators.iloc[-21:-1]["high"].max())
    past_close = float(indicators.iloc[-3]["close"])
    recent_surge = (close - past_close) / past_close if past_close > 0 else 0.0
    liquidity_bonus = min(10.0, float(ticker_row["trade_value_24h"]) / 50_000_000_000 * 10.0)

    breakout = (
        settings.enable_volatility_breakout
        and
        regime.name in {"bullish", "neutral"}
        and float(latest["high"]) >= prior_high
        and close >= prior_high * 0.998
        and volume_ratio >= 2.0
        and 0.005 <= change_rate <= 0.08
        and recent_surge < 0.05
    )
    if breakout:
        return StrategyDecision(
            True,
            "volatility_breakout",
            "변동성 돌파",
            min(100.0, 82.0 + liquidity_bonus),
            settings.breakout_position_size_ratio,
            "강한 돌파",
            rsi,
            ["최근 20봉 최고가를 거래량 2배 이상으로 돌파했습니다.", regime.reason],
            ["돌파 실패 시 빠른 되돌림이 발생할 수 있습니다."],
        )

    pullback_precheck = (
        settings.enable_trend_pullback
        and regime.name == "bullish"
        and 40 <= rsi <= 55
        and rsi > float(previous["rsi"])
        and close > float(latest["ma_mid"])
        and volume_ratio >= 1.10
        and change_rate <= 0.06
    )
    if pullback_precheck and _higher_timeframe_uptrend(client, market):
        return StrategyDecision(
            True,
            "trend_pullback",
            "추세 눌림목",
            min(100.0, 80.0 + liquidity_bonus),
            settings.pullback_position_size_ratio,
            "상승 추세 조정 후 반등",
            rsi,
            ["15분·60분 상승 추세에서 5분봉 조정 후 RSI가 반등했습니다.", regime.reason],
            [],
        )

    trend_confirmation = (
        settings.enable_trend_confirmation
        and regime.name == "bullish"
        and float(latest["ma_short"]) > float(latest["ma_mid"]) > float(latest["ma_long"])
        and close > float(latest["ma_long"])
        and volume_ratio >= settings.min_entry_volume_ratio
        and settings.min_entry_rsi <= rsi <= settings.max_entry_rsi
        and settings.min_entry_change_rate <= change_rate <= settings.max_entry_change_rate
        and recent_surge < settings.max_recent_surge_rate
    )
    if trend_confirmation:
        return StrategyDecision(
            True,
            "trend_confirmation",
            "다중 조건 추세",
            min(100.0, 78.0 + liquidity_bonus),
            settings.trend_position_size_ratio,
            "상승 추세 확인",
            rsi,
            ["이동평균·거래량·RSI·급등 방지 조건을 모두 통과했습니다.", regime.reason],
            [],
        )

    mean_reversion = (
        settings.enable_mean_reversion
        and regime.name == "range"
        and rsi <= 35
        and float(latest["low"]) <= float(latest["bb_low"])
        and close > float(previous["close"])
        and volume_ratio >= 0.80
    )
    if mean_reversion:
        return StrategyDecision(
            True,
            "mean_reversion",
            "횡보장 평균회귀",
            min(100.0, 78.0 + liquidity_bonus),
            settings.mean_reversion_position_size_ratio,
            "과매도 반등",
            rsi,
            ["횡보장에서 볼린저밴드 하단을 확인한 뒤 가격이 반등했습니다.", regime.reason],
            ["추세 하락으로 전환되면 평균회귀가 실패할 수 있습니다."],
        )

    return StrategyDecision(
        False,
        rsi=rsi,
        risks=[f"{regime.label}에서 활성 전략의 필수 진입조건을 충족하지 못했습니다."],
    )

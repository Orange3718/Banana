from __future__ import annotations

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator, MACD
from ta.volatility import AverageTrueRange, BollingerBands


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, window: int) -> pd.Series:
    return series.ewm(span=window, adjust=False).mean()


def rsi(series: pd.Series, window: int = 14) -> pd.Series:
    return RSIIndicator(close=series, window=window).rsi()


def macd(series: pd.Series) -> pd.DataFrame:
    indicator = MACD(close=series)
    return pd.DataFrame(
        {
            "macd": indicator.macd(),
            "macd_signal": indicator.macd_signal(),
            "macd_diff": indicator.macd_diff(),
        }
    )


def bollinger_bands(series: pd.Series, window: int = 20, window_dev: int = 2) -> pd.DataFrame:
    indicator = BollingerBands(close=series, window=window, window_dev=window_dev)
    return pd.DataFrame(
        {
            "bb_high": indicator.bollinger_hband(),
            "bb_mid": indicator.bollinger_mavg(),
            "bb_low": indicator.bollinger_lband(),
            "bb_width": indicator.bollinger_wband(),
        }
    )


def atr(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    return AverageTrueRange(high=high, low=low, close=close, window=window).average_true_range()


def adx(high: pd.Series, low: pd.Series, close: pd.Series, window: int = 14) -> pd.Series:
    return ADXIndicator(high=high, low=low, close=close, window=window).adx()


def volume_ma(volume: pd.Series, window: int = 20) -> pd.Series:
    return volume.rolling(window=window, min_periods=window).mean()


def add_indicators(
    df: pd.DataFrame,
    ma_short: int,
    ma_mid: int,
    ma_long: int,
    rsi_period: int,
) -> pd.DataFrame:
    """Return a new candle dataframe with all strategy indicators attached."""
    data = df.copy()
    data["ma_short"] = sma(data["close"], ma_short)
    data["ma_mid"] = sma(data["close"], ma_mid)
    data["ma_long"] = sma(data["close"], ma_long)
    data["ema_short"] = ema(data["close"], ma_short)
    data["rsi"] = rsi(data["close"], rsi_period)
    data["volume_ma20"] = volume_ma(data["volume"], 20)
    data["atr"] = atr(data["high"], data["low"], data["close"], 14)
    data["adx"] = adx(data["high"], data["low"], data["close"], 14)

    macd_df = macd(data["close"])
    bb_df = bollinger_bands(data["close"], 20, 2)
    return pd.concat([data, macd_df, bb_df], axis=1)

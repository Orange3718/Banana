from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import pandas as pd

from config import Config
from settings_store import TradingSettings

Action = Literal["BUY", "SELL", "HOLD"]


@dataclass
class Position:
    market: str
    currency: str
    volume: float = 0.0
    avg_buy_price: float = 0.0
    buy_count: int = 0
    first_profit_taken: bool = False
    highest_profit_rate: float = 0.0

    @property
    def has_position(self) -> bool:
        return self.volume > 0 and self.avg_buy_price > 0

    def profit_rate(self, current_price: float) -> float:
        if not self.has_position:
            return 0.0
        return (current_price - self.avg_buy_price) / self.avg_buy_price


@dataclass
class Signal:
    action: Action
    reason: str
    confidence: float = 0.0
    buy_ratio: float = 0.0
    sell_ratio: float = 0.0

    def to_dict(self) -> dict[str, float | str]:
        return {
            "action": self.action,
            "reason": self.reason,
            "confidence": self.confidence,
            "buy_ratio": self.buy_ratio,
            "sell_ratio": self.sell_ratio,
        }


class MovingAverageStrategy:
    def __init__(self, config: Config, settings: TradingSettings | None = None):
        self.config = config
        self.settings = settings or TradingSettings()

    def generate_signal(self, market_data: pd.DataFrame, position: Position) -> dict[str, float | str]:
        if len(market_data) < 2:
            return Signal("HOLD", "Not enough indicator data").to_dict()

        latest = market_data.iloc[-1]
        prev = market_data.iloc[-2]
        current_price = float(latest["close"])
        profit_rate = position.profit_rate(current_price)

        if position.has_position:
            sell_signal = self._sell_signal(latest, prev, position, profit_rate)
            if sell_signal.action != "HOLD":
                return sell_signal.to_dict()

        buy_signal = self._buy_signal(market_data, latest, prev, position)
        return buy_signal.to_dict()

    def _buy_signal(
        self,
        market_data: pd.DataFrame,
        latest: pd.Series,
        prev: pd.Series,
        position: Position,
    ) -> Signal:
        current_price = float(latest["close"])
        rsi_value = float(latest["rsi"])
        volume = float(latest["volume"])
        volume_avg = float(latest["volume_ma20"])
        surge_rate = self._recent_surge_rate(market_data, minutes=10)
        crossed_up = float(prev["ma_short"]) <= float(prev["ma_mid"]) and float(latest["ma_short"]) > float(latest["ma_mid"])
        rsi_buy_limit = self.settings.effective_rsi_buy_limit(self.config.rsi_buy_limit)
        volume_threshold = volume_avg * self.settings.volume_multiplier()
        surge_limit = self.settings.recent_surge_limit()
        buy_ratio = min(1.0, self.config.buy_amount_ratio * self.settings.buy_ratio_multiplier())

        if position.buy_count >= self.config.max_buy_count:
            return Signal("HOLD", "Maximum buy count reached")
        if rsi_value > rsi_buy_limit:
            return Signal("HOLD", f"RSI too high: {rsi_value:.2f}")
        if volume <= volume_threshold:
            return Signal("HOLD", "Volume is below recent average")
        if surge_rate >= surge_limit:
            return Signal("HOLD", f"Recent 10-minute surge is too high: {surge_rate:.2%}")

        if position.has_position:
            drop_rate = (position.avg_buy_price - current_price) / position.avg_buy_price
            next_index = max(position.buy_count - 1, 0)
            if next_index < len(self.config.add_buy_drop_rates) and drop_rate >= self.config.add_buy_drop_rates[next_index]:
                ratio = min(1.0, (0.3 if position.buy_count == 1 else 0.4) * self.settings.buy_ratio_multiplier())
                return Signal("BUY", f"Additional buy condition met: drop {drop_rate:.2%}", 0.80, ratio, 0.0)
            return Signal("HOLD", "Holding existing position")

        base_conditions = [
            current_price > float(latest["ma_long"]),
            float(latest["ma_short"]) > float(latest["ma_mid"]),
            rsi_value < rsi_buy_limit,
            volume > volume_threshold,
            surge_rate < surge_limit,
        ]
        if all(base_conditions):
            confidence = 0.92 if crossed_up else 0.76
            reason = "MA short crossed above MA mid with volume increase" if crossed_up else "MA trend and volume conditions met"
            return Signal("BUY", reason, confidence, buy_ratio, 0.0)

        return Signal("HOLD", "Buy conditions not met")

    def _sell_signal(
        self,
        latest: pd.Series,
        prev: pd.Series,
        position: Position,
        profit_rate: float,
    ) -> Signal:
        crossed_down = float(prev["ma_short"]) >= float(prev["ma_mid"]) and float(latest["ma_short"]) < float(latest["ma_mid"])
        trailing_drop = position.highest_profit_rate - profit_rate

        if profit_rate <= -self.settings.stop_loss_rate:
            return Signal("SELL", f"Stop loss reached: {profit_rate:.2%}", 0.95, 0.0, 1.0)
        if profit_rate >= self.settings.take_profit_rate_2:
            return Signal("SELL", f"Second take profit reached: {profit_rate:.2%}", 0.90, 0.0, 1.0)
        if profit_rate >= self.settings.take_profit_rate_1 and not position.first_profit_taken:
            return Signal("SELL", f"First take profit reached: {profit_rate:.2%}", 0.85, 0.0, self.config.take_profit_sell_ratio_1)
        if crossed_down:
            return Signal("SELL", "MA short crossed below MA mid", 0.82, 0.0, 1.0)
        if (
            position.highest_profit_rate >= self.settings.trailing_activation_rate
            and trailing_drop >= self.settings.trailing_stop_rate
        ):
            return Signal("SELL", f"Trailing stop triggered: drop {trailing_drop:.2%}", 0.88, 0.0, 1.0)

        return Signal("HOLD", "Sell conditions not met")

    def _recent_surge_rate(self, market_data: pd.DataFrame, minutes: int = 10) -> float:
        candles = max(1, minutes // 5) if self.config.interval.startswith("minute5") else 2
        if len(market_data) <= candles:
            return 0.0
        past_price = float(market_data.iloc[-candles - 1]["close"])
        current_price = float(market_data.iloc[-1]["close"])
        if past_price <= 0:
            return 0.0
        return (current_price - past_price) / past_price

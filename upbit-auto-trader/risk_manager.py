from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, TYPE_CHECKING

from config import Config
if TYPE_CHECKING:
    from strategy import Position


@dataclass
class RiskDecision:
    allowed: bool
    reason: str


@dataclass
class RiskManager:
    config: Config
    daily_start_equity: float | None = None
    daily_realized_pnl: float = 0.0
    current_day: date = field(default_factory=date.today)
    pending_order: bool = False
    api_available: bool = True

    def reset_daily_if_needed(self) -> None:
        today = date.today()
        if today != self.current_day:
            self.current_day = today
            self.daily_start_equity = None
            self.daily_realized_pnl = 0.0

    def set_api_available(self, available: bool) -> None:
        self.api_available = available

    def validate(
        self,
        signal: dict[str, Any],
        position: Position,
        available_krw: float,
        current_price: float,
        total_equity: float,
    ) -> RiskDecision:
        self.reset_daily_if_needed()
        action = signal.get("action", "HOLD")

        if action == "HOLD":
            return RiskDecision(False, "Signal is HOLD")
        if not self.api_available:
            return RiskDecision(False, "API is not available")
        if self.pending_order:
            return RiskDecision(False, "Duplicate order blocked because another order is pending")
        if self.daily_start_equity is None:
            self.daily_start_equity = max(total_equity, 1.0)

        daily_loss_rate = max(0.0, (self.daily_start_equity - total_equity) / self.daily_start_equity)
        if action == "BUY" and daily_loss_rate >= self.config.max_daily_loss:
            return RiskDecision(False, f"Daily max loss exceeded: {daily_loss_rate:.2%}")

        if action == "BUY":
            return self._validate_buy(signal, position, available_krw, current_price, total_equity)
        if action == "SELL":
            return self._validate_sell(signal, position, current_price)
        return RiskDecision(False, f"Unknown action: {action}")

    def _validate_buy(
        self,
        signal: dict[str, Any],
        position: Position,
        available_krw: float,
        current_price: float,
        total_equity: float,
    ) -> RiskDecision:
        if position.buy_count >= self.config.max_buy_count:
            return RiskDecision(False, "Maximum buy count reached")

        buy_ratio = float(signal.get("buy_ratio", 0))
        order_krw = available_krw * buy_ratio
        if order_krw < self.config.min_order_krw:
            return RiskDecision(False, f"Order amount below minimum: {order_krw:,.0f} KRW")
        if order_krw > available_krw:
            return RiskDecision(False, "Insufficient KRW balance")

        current_position_value = position.volume * current_price
        max_position_value = total_equity * self.config.max_position_krw_ratio
        if current_position_value + order_krw > max_position_value:
            return RiskDecision(False, "Maximum position size exceeded")

        return RiskDecision(True, "Buy risk checks passed")

    def _validate_sell(self, signal: dict[str, Any], position: Position, current_price: float) -> RiskDecision:
        if not position.has_position:
            return RiskDecision(False, "No position to sell")

        sell_ratio = float(signal.get("sell_ratio", 0))
        sell_value = position.volume * sell_ratio * current_price
        if sell_value < self.config.min_order_krw and sell_ratio < 1.0:
            return RiskDecision(False, f"Partial sell amount below minimum: {sell_value:,.0f} KRW")

        return RiskDecision(True, "Sell risk checks passed")

    def validate_real_trade_permission(self) -> RiskDecision:
        if self.config.dry_run:
            return RiskDecision(False, "DRY_RUN=true, real order is disabled")
        if not self.config.enable_real_trade:
            return RiskDecision(False, "ENABLE_REAL_TRADE=false, real order is disabled")
        return RiskDecision(True, "Real trading is enabled")

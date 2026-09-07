from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from config import Config
from risk_manager import RiskManager
from strategy import Position
from upbit_client import UpbitClient


@dataclass
class OrderRecord:
    action: str
    market: str
    amount: float
    volume: float
    price: float
    reason: str
    result: dict[str, Any]


@dataclass
class Trader:
    config: Config
    client: UpbitClient
    risk_manager: RiskManager
    logger: logging.Logger
    order_history: list[OrderRecord] = field(default_factory=list)

    def execute_signal(
        self,
        signal: dict[str, Any],
        position: Position,
        available_krw: float,
        current_price: float,
        total_equity: float,
    ) -> dict[str, Any] | None:
        action = str(signal.get("action", "HOLD"))
        risk = self.risk_manager.validate(signal, position, available_krw, current_price, total_equity)
        self.logger.info("Signal=%s | Reason=%s | Risk=%s", action, signal.get("reason"), risk.reason)

        if not risk.allowed:
            return None

        if action == "BUY":
            return self._buy(signal, position, available_krw, current_price)
        if action == "SELL":
            return self._sell(signal, position, current_price)
        return None

    def _buy(
        self,
        signal: dict[str, Any],
        position: Position,
        available_krw: float,
        current_price: float,
    ) -> dict[str, Any] | None:
        buy_ratio = float(signal.get("buy_ratio", 0))
        krw_amount = available_krw * buy_ratio
        estimated_volume = krw_amount / current_price if current_price > 0 else 0.0

        if self.config.dry_run or not self.config.enable_real_trade:
            result = {"dry_run": True, "message": "Market buy skipped", "amount": krw_amount}
            self._record("BUY", krw_amount, estimated_volume, current_price, signal, result)
            self.logger.warning("[DRY_RUN] BUY %s amount=%,.0f KRW reason=%s", self.config.market, krw_amount, signal.get("reason"))
            self._update_position_after_dry_buy(position, krw_amount, estimated_volume, current_price)
            return result

        permission = self.risk_manager.validate_real_trade_permission()
        if not permission.allowed:
            self.logger.warning("Real buy blocked: %s", permission.reason)
            return None

        self.risk_manager.pending_order = True
        try:
            result = self.client.market_buy(self.config.market, krw_amount)
            self._record("BUY", krw_amount, estimated_volume, current_price, signal, result)
            self.logger.info("BUY order sent: %s", result)
            return result
        finally:
            self.risk_manager.pending_order = False

    def _sell(
        self,
        signal: dict[str, Any],
        position: Position,
        current_price: float,
    ) -> dict[str, Any] | None:
        sell_ratio = min(max(float(signal.get("sell_ratio", 0)), 0.0), 1.0)
        volume = position.volume * sell_ratio
        if sell_ratio >= 1.0:
            volume = position.volume
        krw_value = volume * current_price

        if self.config.dry_run or not self.config.enable_real_trade:
            result = {"dry_run": True, "message": "Market sell skipped", "volume": volume}
            self._record("SELL", krw_value, volume, current_price, signal, result)
            self.logger.warning("[DRY_RUN] SELL %s volume=%.8f reason=%s", self.config.market, volume, signal.get("reason"))
            self._update_position_after_dry_sell(position, sell_ratio)
            return result

        permission = self.risk_manager.validate_real_trade_permission()
        if not permission.allowed:
            self.logger.warning("Real sell blocked: %s", permission.reason)
            return None

        self.risk_manager.pending_order = True
        try:
            result = self.client.market_sell(self.config.market, volume)
            self._record("SELL", krw_value, volume, current_price, signal, result)
            self.logger.info("SELL order sent: %s", result)
            return result
        finally:
            self.risk_manager.pending_order = False

    def _update_position_after_dry_buy(
        self,
        position: Position,
        krw_amount: float,
        estimated_volume: float,
        current_price: float,
    ) -> None:
        previous_value = position.volume * position.avg_buy_price if position.has_position else 0.0
        new_value = previous_value + krw_amount
        new_volume = position.volume + estimated_volume
        position.volume = new_volume
        position.avg_buy_price = new_value / new_volume if new_volume > 0 else current_price
        position.buy_count += 1

    def _update_position_after_dry_sell(self, position: Position, sell_ratio: float) -> None:
        if sell_ratio >= 1.0:
            position.volume = 0.0
            position.avg_buy_price = 0.0
            position.buy_count = 0
            position.first_profit_taken = False
            position.highest_profit_rate = 0.0
        else:
            position.volume *= max(0.0, 1.0 - sell_ratio)
            position.first_profit_taken = True

    def _record(
        self,
        action: str,
        amount: float,
        volume: float,
        price: float,
        signal: dict[str, Any],
        result: dict[str, Any],
    ) -> None:
        record = OrderRecord(
            action=action,
            market=self.config.market,
            amount=amount,
            volume=volume,
            price=price,
            reason=str(signal.get("reason", "")),
            result=result,
        )
        self.order_history.append(record)
        self.logger.info("Order record: %s", record)

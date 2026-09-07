from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


def _to_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _to_float_list(value: str | None, default: list[float]) -> list[float]:
    if not value:
        return default
    return [float(item.strip()) for item in value.split(",") if item.strip()]


@dataclass(frozen=True)
class Config:
    access_key: str
    secret_key: str
    base_url: str
    market: str
    interval: str
    candle_count: int
    ma_short: int
    ma_mid: int
    ma_long: int
    rsi_period: int
    rsi_buy_limit: float
    buy_amount_ratio: float
    max_buy_count: int
    add_buy_drop_rates: list[float]
    take_profit_rate_1: float
    take_profit_sell_ratio_1: float
    take_profit_rate_2: float
    stop_loss_rate: float
    trailing_stop_rate: float
    min_order_krw: float
    max_daily_loss: float
    max_position_krw_ratio: float
    paper_initial_krw: float
    loop_interval: int
    dry_run: bool
    enable_real_trade: bool
    notify_steps: bool
    notify_hold_signals: bool
    telegram_bot_token: str
    telegram_allowed_chat_id: str

    @classmethod
    def load(cls, env_path: str | Path = ".env") -> "Config":
        load_dotenv(env_path, override=True, encoding="utf-8-sig")
        config = cls(
            access_key=os.getenv("UPBIT_ACCESS_KEY", ""),
            secret_key=os.getenv("UPBIT_SECRET_KEY", ""),
            base_url=os.getenv("UPBIT_BASE_URL", "https://api.upbit.com").rstrip("/"),
            market=os.getenv("MARKET", "KRW-BTC"),
            interval=os.getenv("INTERVAL", "minute5"),
            candle_count=int(os.getenv("CANDLE_COUNT", "120")),
            ma_short=int(os.getenv("MA_SHORT", "5")),
            ma_mid=int(os.getenv("MA_MID", "20")),
            ma_long=int(os.getenv("MA_LONG", "60")),
            rsi_period=int(os.getenv("RSI_PERIOD", "14")),
            rsi_buy_limit=float(os.getenv("RSI_BUY_LIMIT", "70")),
            buy_amount_ratio=float(os.getenv("BUY_AMOUNT_RATIO", "0.30")),
            max_buy_count=int(os.getenv("MAX_BUY_COUNT", "3")),
            add_buy_drop_rates=_to_float_list(os.getenv("ADD_BUY_DROP_RATES"), [0.02, 0.04]),
            take_profit_rate_1=float(os.getenv("TAKE_PROFIT_RATE_1", "0.03")),
            take_profit_sell_ratio_1=float(os.getenv("TAKE_PROFIT_SELL_RATIO_1", "0.50")),
            take_profit_rate_2=float(os.getenv("TAKE_PROFIT_RATE_2", "0.05")),
            stop_loss_rate=float(os.getenv("STOP_LOSS_RATE", "0.03")),
            trailing_stop_rate=float(os.getenv("TRAILING_STOP_RATE", "0.02")),
            min_order_krw=float(os.getenv("MIN_ORDER_KRW", "5000")),
            max_daily_loss=float(os.getenv("MAX_DAILY_LOSS", "0.05")),
            max_position_krw_ratio=float(os.getenv("MAX_POSITION_KRW_RATIO", "0.90")),
            paper_initial_krw=float(os.getenv("PAPER_INITIAL_KRW", "1000000")),
            loop_interval=int(os.getenv("LOOP_INTERVAL", "10")),
            dry_run=_to_bool(os.getenv("DRY_RUN"), True),
            enable_real_trade=_to_bool(os.getenv("ENABLE_REAL_TRADE"), False),
            notify_steps=_to_bool(os.getenv("NOTIFY_STEPS"), True),
            notify_hold_signals=_to_bool(os.getenv("NOTIFY_HOLD_SIGNALS"), False),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN", ""),
            telegram_allowed_chat_id=os.getenv("TELEGRAM_ALLOWED_CHAT_ID", ""),
        )
        config.validate()
        return config

    @property
    def quote_currency(self) -> str:
        return self.market.split("-")[0]

    @property
    def base_currency(self) -> str:
        return self.market.split("-")[1]

    @property
    def real_trade_enabled(self) -> bool:
        return (not self.dry_run) and self.enable_real_trade

    def validate(self) -> None:
        errors: list[str] = []

        if "-" not in self.market:
            errors.append("MARKET must look like KRW-BTC.")
        if self.candle_count < max(self.ma_long, self.rsi_period, 20):
            errors.append("CANDLE_COUNT must be large enough for the longest indicator window.")
        if not (0 < self.ma_short < self.ma_mid < self.ma_long):
            errors.append("MA_SHORT, MA_MID, MA_LONG must be increasing positive values.")
        for name, value in {
            "BUY_AMOUNT_RATIO": self.buy_amount_ratio,
            "TAKE_PROFIT_SELL_RATIO_1": self.take_profit_sell_ratio_1,
            "MAX_DAILY_LOSS": self.max_daily_loss,
            "MAX_POSITION_KRW_RATIO": self.max_position_krw_ratio,
        }.items():
            if not 0 < value <= 1:
                errors.append(f"{name} must be greater than 0 and less than or equal to 1.")
        if self.max_buy_count < 1:
            errors.append("MAX_BUY_COUNT must be at least 1.")
        if self.min_order_krw <= 0:
            errors.append("MIN_ORDER_KRW must be positive.")
        if self.loop_interval < 1:
            errors.append("LOOP_INTERVAL must be at least 1 second.")
        if self.real_trade_enabled and (not self.access_key or not self.secret_key):
            errors.append("Real trading requires UPBIT_ACCESS_KEY and UPBIT_SECRET_KEY.")

        if errors:
            raise ValueError("Invalid configuration: " + " ".join(errors))

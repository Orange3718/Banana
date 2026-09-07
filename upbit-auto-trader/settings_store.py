from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


SETTINGS_PATH = Path(__file__).resolve().parent / "trading_settings.json"
TRADING_STYLES = {
    "conservative": {
        "label": "보수적",
        "description": "거래 빈도를 줄이고 높은 확률의 후보만 기다립니다.",
    },
    "balanced": {
        "label": "균형",
        "description": "기본 조건을 유지하며 과도한 매매를 피합니다.",
    },
    "aggressive": {
        "label": "적극적",
        "description": "더 많은 후보를 보고, 진입 조건을 조금 완화해 기회를 자주 찾습니다.",
    },
}


@dataclass
class TradingSettings:
    operation_mode: int = 1
    trading_style: str = "balanced"
    approval_required: bool = True
    recommendation_enabled: bool = True
    include_btc: bool = False
    recommendation_count: int = 3
    scanner_market_limit: int = 25
    min_recommendation_score: float = 75.0
    min_24h_trade_value_krw: float = 5_000_000_000.0
    max_change_rate_abs: float = 0.20
    total_capital_krw: float = 500_000.0
    buy_amount_krw: float = 20_000.0
    per_coin_max_krw: float = 40_000.0
    max_positions: int = 4
    max_daily_trades: int = 5
    stop_loss_rate: float = 0.025
    take_profit_rate_1: float = 0.025
    take_profit_rate_2: float = 0.045
    trailing_stop_rate: float = 0.015
    trailing_activation_rate: float = 0.02
    min_cash_reserve_krw: float = 100_000.0
    min_cash_reserve_ratio: float = 0.20
    max_daily_loss_rate: float = 0.015
    loss_cooldown_minutes: int = 240
    profit_cooldown_minutes: int = 60
    max_consecutive_losses: int = 3
    loss_pause_minutes: int = 60
    min_entry_rsi: float = 48.0
    max_entry_rsi: float = 65.0
    min_entry_volume_ratio: float = 1.5
    min_entry_change_rate: float = 0.005
    max_entry_change_rate: float = 0.06
    max_recent_surge_rate: float = 0.03
    enable_trend_confirmation: bool = True
    enable_trend_pullback: bool = True
    enable_volatility_breakout: bool = True
    enable_mean_reversion: bool = True
    trend_position_size_ratio: float = 1.0
    pullback_position_size_ratio: float = 0.75
    breakout_position_size_ratio: float = 0.50
    mean_reversion_position_size_ratio: float = 0.50
    notify_recommendations: bool = True
    notify_approval_requests: bool = True
    notify_order_results: bool = True
    periodic_report_minutes: int = 60
    daily_review_time: str = "21:00"

    @property
    def mode_label(self) -> str:
        labels = {
            1: "1단계 추천 전용",
            2: "2단계 승인형 실제 추천 매매",
            3: "3단계 그룹 제한 자동매매",
            4: "4단계 완전 자동 운영",
        }
        return labels.get(self.operation_mode, "알 수 없음")

    @property
    def style_label(self) -> str:
        return TRADING_STYLES.get(self.trading_style, TRADING_STYLES["balanced"])["label"]

    @property
    def style_description(self) -> str:
        return TRADING_STYLES.get(self.trading_style, TRADING_STYLES["balanced"])["description"]

    def effective_min_recommendation_score(self) -> float:
        if self.trading_style == "conservative":
            return min(100.0, self.min_recommendation_score + 10.0)
        return self.min_recommendation_score

    def effective_min_24h_trade_value_krw(self) -> float:
        if self.trading_style == "aggressive":
            return self.min_24h_trade_value_krw * 0.6
        if self.trading_style == "conservative":
            return self.min_24h_trade_value_krw * 1.5
        return self.min_24h_trade_value_krw

    def effective_max_change_rate_abs(self) -> float:
        if self.trading_style == "aggressive":
            return min(1.0, self.max_change_rate_abs * 1.5)
        if self.trading_style == "conservative":
            return max(0.01, self.max_change_rate_abs * 0.75)
        return self.max_change_rate_abs

    def effective_rsi_buy_limit(self, base_limit: float) -> float:
        if self.trading_style == "aggressive":
            return min(85.0, max(base_limit, base_limit + 8.0))
        if self.trading_style == "conservative":
            return max(45.0, min(base_limit, base_limit - 8.0))
        return base_limit

    def volume_multiplier(self) -> float:
        if self.trading_style == "aggressive":
            return 0.75
        if self.trading_style == "conservative":
            return 1.15
        return 1.0

    def recent_surge_limit(self) -> float:
        if self.trading_style == "aggressive":
            return 0.08
        if self.trading_style == "conservative":
            return 0.035
        return 0.05

    def buy_ratio_multiplier(self) -> float:
        if self.trading_style == "aggressive":
            return 1.2
        if self.trading_style == "conservative":
            return 0.75
        return 1.0

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.operation_mode not in {1, 2, 3, 4}:
            errors.append("운영 단계는 1~4 사이여야 합니다.")
        if self.trading_style not in TRADING_STYLES:
            errors.append("거래 성향은 보수적/균형/적극적 중 하나여야 합니다.")
        if self.recommendation_count < 1:
            errors.append("추천 코인 수는 1개 이상이어야 합니다.")
        if self.scanner_market_limit < self.recommendation_count:
            errors.append("스캔 코인 수는 추천 코인 수보다 크거나 같아야 합니다.")
        if self.buy_amount_krw <= 0:
            errors.append("1회 매수 금액은 0보다 커야 합니다.")
        if self.per_coin_max_krw < self.buy_amount_krw:
            errors.append("코인당 최대 투자금은 1회 매수 금액보다 크거나 같아야 합니다.")
        if self.total_capital_krw < self.buy_amount_krw:
            errors.append("총 운용금액은 1회 매수 금액보다 크거나 같아야 합니다.")
        if self.max_positions < 1:
            errors.append("자동매매 최대 보유 종목 수는 1개 이상이어야 합니다.")
        if self.max_daily_trades < 1:
            errors.append("하루 최대 매수 횟수는 1회 이상이어야 합니다.")
        if not 0 <= self.min_cash_reserve_ratio <= 1:
            errors.append("현금 보유 비율은 0 이상 1 이하여야 합니다.")
        if not 0 < self.max_daily_loss_rate <= 1:
            errors.append("하루 계좌 손실 제한은 0보다 크고 1 이하여야 합니다.")
        if not 0 <= self.min_entry_rsi < self.max_entry_rsi <= 100:
            errors.append("진입 RSI 범위를 확인해 주세요.")
        if self.min_entry_volume_ratio <= 0:
            errors.append("진입 거래량 배수는 0보다 커야 합니다.")
        if not -1 < self.min_entry_change_rate < self.max_entry_change_rate < 1:
            errors.append("진입 등락률 범위를 확인해 주세요.")
        for name, value in {
            "추세 주문배수": self.trend_position_size_ratio,
            "눌림목 주문배수": self.pullback_position_size_ratio,
            "돌파 주문배수": self.breakout_position_size_ratio,
            "평균회귀 주문배수": self.mean_reversion_position_size_ratio,
        }.items():
            if not 0 < value <= 1:
                errors.append(f"{name}는 0보다 크고 1 이하여야 합니다.")
        for name, value in {
            "손절률": self.stop_loss_rate,
            "1차 익절률": self.take_profit_rate_1,
            "2차 익절률": self.take_profit_rate_2,
            "트레일링 스탑": self.trailing_stop_rate,
            "트레일링 활성화 수익률": self.trailing_activation_rate,
            "최근 급등률": self.max_recent_surge_rate,
            "최대 변동률 필터": self.max_change_rate_abs,
        }.items():
            if not 0 < value <= 1:
                errors.append(f"{name}은 0보다 크고 1 이하여야 합니다.")
        return errors


def _atomic_write(path: Path, payload: str) -> None:
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temp_path.write_text(payload, encoding="utf-8")
    os.replace(temp_path, path)


def load_settings(path: Path = SETTINGS_PATH) -> TradingSettings:
    if not path.exists():
        settings = TradingSettings()
        save_settings(settings, path)
        return settings
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        settings = TradingSettings()
        save_settings(settings, path)
        return settings

    default = asdict(TradingSettings())
    default.update({key: value for key, value in data.items() if key in default})
    return TradingSettings(**default)


def save_settings(settings: TradingSettings, path: Path = SETTINGS_PATH) -> TradingSettings:
    errors = settings.validate()
    if errors:
        raise ValueError(" ".join(errors))
    _atomic_write(path, json.dumps(asdict(settings), ensure_ascii=False, indent=2))
    return settings


def update_settings(**changes: Any) -> TradingSettings:
    settings = load_settings()
    data = asdict(settings)
    data.update({key: value for key, value in changes.items() if key in data})
    return save_settings(TradingSettings(**data))

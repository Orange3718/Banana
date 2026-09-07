from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


STATE_PATH = Path(__file__).resolve().parent / "recommendation_state.json"
HISTORY_PATH = Path(__file__).resolve().parent / "trade_history.jsonl"


@dataclass
class Recommendation:
    market: str
    score: float
    price: float
    change_rate: float
    trade_value_24h: float
    rsi: float
    trend: str
    reasons: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    group: str = "watch"
    strategy_name: str = "trend_confirmation"
    strategy_label: str = "다중 조건 추세"
    market_regime: str = ""
    position_size_ratio: float = 1.0
    approved: bool = False
    rejected: bool = False
    user_reason: str = ""


@dataclass
class RecommendationState:
    generated_at: str = ""
    recommendations: list[Recommendation] = field(default_factory=list)
    pending_market: str = ""
    last_decision: str = ""
    market_regime: str = ""
    market_regime_reason: str = ""


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _atomic_write(path: Path, payload: str) -> None:
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temp_path.write_text(payload, encoding="utf-8")
    os.replace(temp_path, path)


def load_recommendation_state(path: Path = STATE_PATH) -> RecommendationState:
    if not path.exists():
        return RecommendationState()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return RecommendationState()
    recs = [Recommendation(**item) for item in data.get("recommendations", []) if isinstance(item, dict)]
    return RecommendationState(
        generated_at=str(data.get("generated_at", "")),
        recommendations=recs,
        pending_market=str(data.get("pending_market", "")),
        last_decision=str(data.get("last_decision", "")),
        market_regime=str(data.get("market_regime", "")),
        market_regime_reason=str(data.get("market_regime_reason", "")),
    )


def save_recommendation_state(state: RecommendationState, path: Path = STATE_PATH) -> RecommendationState:
    payload = {
        "generated_at": state.generated_at or now_text(),
        "recommendations": [asdict(item) for item in state.recommendations],
        "pending_market": state.pending_market,
        "last_decision": state.last_decision,
        "market_regime": state.market_regime,
        "market_regime_reason": state.market_regime_reason,
    }
    _atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2))
    return state


def find_recommendation(market: str) -> Recommendation | None:
    state = load_recommendation_state()
    for rec in state.recommendations:
        if rec.market == market:
            return rec
    return None


def append_history(event: str, payload: dict[str, Any], path: Path = HISTORY_PATH) -> None:
    record = {
        "time": now_text(),
        "event": event,
        **payload,
    }
    with path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")

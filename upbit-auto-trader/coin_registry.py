from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


REGISTRY_PATH = Path(__file__).resolve().parent / "coin_registry.json"


GROUP_POLICIES = {
    "major": "대형 코인: 승인형 또는 제한 자동매매 후보",
    "volume": "거래량 상위: 승인형 추천 후보",
    "watch": "관찰 그룹: 추천만 우선 표시",
    "high_risk": "고위험 관찰: 자동매매 금지",
    "excluded": "사용자 제외: 감시/추천/매매 제외",
}

SPECIAL_DEFAULT_EXCLUDED = {"KRW-USDT", "KRW-USDC"}


@dataclass
class CoinEntry:
    market: str
    korean_name: str = ""
    english_name: str = ""
    group: str = "watch"
    watch: bool = True
    allow_recommend: bool = True
    allow_telegram_approval: bool = True
    allow_auto_trade: bool = False
    excluded: bool = False
    note: str = ""


def _atomic_write(path: Path, payload: str) -> None:
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temp_path.write_text(payload, encoding="utf-8")
    os.replace(temp_path, path)


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, CoinEntry]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    registry: dict[str, CoinEntry] = {}
    for market, item in data.items():
        if isinstance(item, dict):
            default = asdict(CoinEntry(market=market))
            default.update({key: value for key, value in item.items() if key in default})
            registry[market] = CoinEntry(**default)
    return registry


def save_registry(registry: dict[str, CoinEntry], path: Path = REGISTRY_PATH) -> dict[str, CoinEntry]:
    payload = {market: asdict(entry) for market, entry in sorted(registry.items())}
    _atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2))
    return registry


def sync_markets(markets: list[dict[str, Any]], path: Path = REGISTRY_PATH) -> dict[str, CoinEntry]:
    registry = load_registry(path)
    for item in markets:
        market = str(item.get("market", ""))
        if not market.startswith("KRW-"):
            continue
        if market not in registry:
            is_special = market in SPECIAL_DEFAULT_EXCLUDED
            group = "major" if market in {"KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL"} else "watch"
            registry[market] = CoinEntry(
                market=market,
                korean_name=str(item.get("korean_name", "")),
                english_name=str(item.get("english_name", "")),
                group="excluded" if is_special else group,
                watch=not is_special,
                allow_recommend=not is_special,
                allow_telegram_approval=not is_special,
                allow_auto_trade=False,
                excluded=is_special,
                note="기본 제외 특수 코인" if is_special else "",
            )
        else:
            registry[market].korean_name = str(item.get("korean_name", registry[market].korean_name))
            registry[market].english_name = str(item.get("english_name", registry[market].english_name))
            if market in SPECIAL_DEFAULT_EXCLUDED and not registry[market].note:
                registry[market].group = "excluded"
                registry[market].watch = False
                registry[market].allow_recommend = False
                registry[market].allow_telegram_approval = False
                registry[market].allow_auto_trade = False
                registry[market].excluded = True
                registry[market].note = "기본 제외 특수 코인"
    save_registry(registry, path)
    return registry


def eligible_markets(registry: dict[str, CoinEntry], *, include_btc: bool) -> list[str]:
    markets: list[str] = []
    for market, entry in registry.items():
        if market == "KRW-BTC" and not include_btc:
            continue
        if entry.excluded or not entry.watch or not entry.allow_recommend:
            continue
        markets.append(market)
    return sorted(markets)


def set_coin_policy(market: str, **changes: Any) -> CoinEntry:
    registry = load_registry()
    entry = registry.get(market, CoinEntry(market=market))
    for key, value in changes.items():
        if hasattr(entry, key):
            setattr(entry, key, value)
    if entry.excluded:
        entry.watch = False
        entry.allow_recommend = False
        entry.allow_telegram_approval = False
        entry.allow_auto_trade = False
        entry.group = "excluded"
    registry[market] = entry
    save_registry(registry)
    return entry

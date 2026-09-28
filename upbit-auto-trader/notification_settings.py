from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


SETTINGS_PATH = Path(__file__).resolve().parent / "notification_settings.json"
RUNTIME_PATH = Path(__file__).resolve().parent / "notification_runtime.json"


@dataclass
class NotificationRule:
    key: str
    label: str
    enabled: bool
    order: int
    min_interval_seconds: int
    description: str


DEFAULT_RULES: tuple[NotificationRule, ...] = (
    NotificationRule("approval_request", "승인 요청", True, 1, 0, "매매 후보를 사용자에게 물어보는 핵심 알림입니다."),
    NotificationRule("order_result", "주문 결과", True, 2, 0, "실제/모의 주문 결과를 알립니다."),
    NotificationRule("risk_alert", "위험/오류", True, 3, 0, "API 오류, 킬 스위치, 주문 차단 같은 위험 알림입니다."),
    NotificationRule("recommendation", "추천 갱신", True, 4, 1800, "추천 목록이 갱신되었을 때 알립니다."),
    NotificationRule("signal", "매매 신호", False, 5, 1800, "BUY/SELL/HOLD 신호를 알립니다. 기본은 꺼짐입니다."),
    NotificationRule("market_snapshot", "시세/포지션", False, 6, 3600, "현재가, 보유수량, 손익률 같은 요약입니다."),
    NotificationRule("worker_step", "워커 단계", False, 7, 3600, "API 확인, 지표 계산 같은 상세 단계입니다. 폭주 방지를 위해 기본 OFF입니다."),
    NotificationRule("daily_review", "일일 복기", True, 8, 0, "매일 저녁 복기 리포트입니다."),
)


def _atomic_write(path: Path, payload: str) -> None:
    temp_path = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temp_path.write_text(payload, encoding="utf-8")
    os.replace(temp_path, path)


def _default_map() -> dict[str, NotificationRule]:
    return {rule.key: rule for rule in DEFAULT_RULES}


def load_notification_rules(path: Path = SETTINGS_PATH) -> dict[str, NotificationRule]:
    defaults = _default_map()
    if not path.exists():
        save_notification_rules(defaults, path)
        return defaults
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        save_notification_rules(defaults, path)
        return defaults

    rules = defaults.copy()
    for key, item in data.items():
        if not isinstance(item, dict):
            continue
        base = asdict(rules.get(key, NotificationRule(key, key, False, 99, 3600, "")))
        base.update({field: value for field, value in item.items() if field in base})
        rules[key] = NotificationRule(**base)
    return rules


def save_notification_rules(rules: dict[str, NotificationRule], path: Path = SETTINGS_PATH) -> dict[str, NotificationRule]:
    payload = {key: asdict(rule) for key, rule in sorted(rules.items(), key=lambda item: item[1].order)}
    _atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2))
    return rules


def ordered_rules() -> list[NotificationRule]:
    return sorted(load_notification_rules().values(), key=lambda rule: rule.order)


def _load_runtime() -> dict[str, Any]:
    if not RUNTIME_PATH.exists():
        return {}
    try:
        data = json.loads(RUNTIME_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _save_runtime(data: dict[str, Any]) -> None:
    _atomic_write(RUNTIME_PATH, json.dumps(data, ensure_ascii=False, indent=2))


def should_send(rule_key: str) -> tuple[bool, str]:
    rules = load_notification_rules()
    rule = rules.get(rule_key)
    if rule is None:
        return False, f"알 수 없는 알림 유형: {rule_key}"
    if not rule.enabled:
        return False, "알림 유형이 꺼져 있습니다."
    runtime = _load_runtime()
    now = time.time()
    last_sent = float(runtime.get(rule_key, 0) or 0)
    if rule.min_interval_seconds > 0 and now - last_sent < rule.min_interval_seconds:
        remain = int(rule.min_interval_seconds - (now - last_sent))
        return False, f"최소 간격 대기 중: {remain}초"
    runtime[rule_key] = now
    _save_runtime(runtime)
    return True, "전송 가능"

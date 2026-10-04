from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


STATE_PATH = Path(__file__).resolve().parent / "runtime_state.json"


@dataclass
class RuntimeState:
    paused: bool = True
    kill_switch: bool = False
    last_command: str = "initialized"
    last_command_source: str = "system"
    last_updated: str = ""
    last_heartbeat: str = ""
    last_status: str = "waiting"
    last_step: str = ""
    last_market: str = ""
    operating_scope: str = "업비트 KRW 마켓 전체"
    strategy_market: str = ""
    managed_coin_count: int = 0
    last_price: float = 0.0
    last_signal: str = "HOLD"
    last_signal_reason: str = ""
    available_krw: float = 0.0
    total_equity: float = 0.0
    position_volume: float = 0.0
    avg_buy_price: float = 0.0
    profit_rate: float = 0.0
    buy_count: int = 0
    last_order_action: str = ""
    last_order_result: str = ""
    dry_run: bool = True
    real_trade_enabled: bool = False


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _default_state() -> RuntimeState:
    state = RuntimeState(last_updated=_now(), last_heartbeat=_now())
    return state


def load_state() -> RuntimeState:
    if not STATE_PATH.exists():
        state = _default_state()
        save_state(state)
        return state

    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        state = _default_state()
        save_state(state)
        return state

    default = asdict(_default_state())
    default.update({key: value for key, value in data.items() if key in default})
    return RuntimeState(**default)


def save_state(state: RuntimeState) -> RuntimeState:
    state.last_updated = _now()
    payload = json.dumps(asdict(state), ensure_ascii=False, indent=2)
    last_error: OSError | None = None
    for attempt in range(3):
        temp_path = STATE_PATH.with_name(f"{STATE_PATH.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp")
        try:
            temp_path.write_text(payload, encoding="utf-8")
            os.replace(temp_path, STATE_PATH)
            return state
        except OSError as exc:
            last_error = exc
            try:
                temp_path.unlink(missing_ok=True)
            except OSError:
                pass
            time.sleep(0.05 * (attempt + 1))
    if last_error:
        raise last_error
    return state


def update_state(**changes: Any) -> RuntimeState:
    state = load_state()
    for key, value in changes.items():
        if hasattr(state, key):
            setattr(state, key, value)
    return save_state(state)


def set_command(command: str, source: str = "dashboard") -> RuntimeState:
    normalized = command.strip().lower()
    changes: dict[str, Any] = {
        "last_command": normalized,
        "last_command_source": source,
    }

    if normalized in {"pause", "stop"}:
        changes.update(paused=True, last_status="paused")
    elif normalized in {"resume", "start"}:
        changes.update(paused=False, kill_switch=False, last_status="running")
    elif normalized in {"kill", "killswitch"}:
        changes.update(paused=True, kill_switch=True, last_status="kill switch active")
    elif normalized == "reset":
        changes.update(paused=True, kill_switch=False, last_status="reset")

    return update_state(**changes)


def update_market_status(
    *,
    market: str,
    price: float,
    signal: str,
    reason: str,
    dry_run: bool,
    real_trade_enabled: bool,
    available_krw: float = 0.0,
    total_equity: float = 0.0,
    position_volume: float = 0.0,
    avg_buy_price: float = 0.0,
    profit_rate: float = 0.0,
    buy_count: int = 0,
    status: str = "running",
    operating_scope: str = "업비트 KRW 마켓 전체",
    strategy_market: str = "",
) -> RuntimeState:
    return update_state(
        last_heartbeat=_now(),
        last_status=status,
        last_market=market,
        operating_scope=operating_scope,
        strategy_market=strategy_market,
        managed_coin_count=int(position_volume),
        last_price=float(price),
        last_signal=signal,
        last_signal_reason=reason,
        available_krw=float(available_krw),
        total_equity=float(total_equity),
        position_volume=float(position_volume),
        avg_buy_price=float(avg_buy_price),
        profit_rate=float(profit_rate),
        buy_count=int(buy_count),
        dry_run=bool(dry_run),
        real_trade_enabled=bool(real_trade_enabled),
    )

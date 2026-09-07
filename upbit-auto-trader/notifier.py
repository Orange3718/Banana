from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

import requests

from config import Config
from notification_settings import should_send
from runtime_state import update_state


ACTION_LABELS = {
    "BUY": "매수",
    "SELL": "매도",
    "HOLD": "대기",
}

REASON_LABELS = {
    "Not enough indicator data": "지표 계산에 필요한 데이터가 부족합니다.",
    "Maximum buy count reached": "최대 매수 횟수에 도달했습니다.",
    "Volume is below recent average": "현재 거래량이 최근 평균 거래량보다 낮습니다.",
    "Holding existing position": "기존 보유 포지션을 유지합니다.",
    "Buy conditions not met": "매수 조건이 충족되지 않았습니다.",
    "Sell conditions not met": "매도 조건이 충족되지 않았습니다.",
    "MA short crossed below MA mid": "단기 이동평균선이 중기 이동평균선을 하향 돌파했습니다.",
}


def korean_action(action: str) -> str:
    return ACTION_LABELS.get(action, action)


def korean_reason(reason: str) -> str:
    for prefix, label in {
        "RSI too high": "RSI가 매수 기준보다 높습니다.",
        "Recent 10-minute surge is too high": "최근 10분 급등 폭이 커서 추격 매수를 막았습니다.",
        "Additional buy condition met": "추가 매수 조건이 충족되었습니다.",
        "MA short crossed above MA mid with volume increase": "단기 이동평균선이 중기 이동평균선을 상향 돌파했고 거래량도 증가했습니다.",
        "MA trend and volume conditions met": "이동평균 추세와 거래량 조건이 충족되었습니다.",
        "Stop loss reached": "손절 기준에 도달했습니다.",
        "Second take profit reached": "2차 익절 기준에 도달했습니다.",
        "First take profit reached": "1차 익절 기준에 도달했습니다.",
        "Trailing stop triggered": "트레일링 스탑 조건이 발동했습니다.",
    }.items():
        if reason.startswith(prefix):
            return label
    return REASON_LABELS.get(reason, reason)


@dataclass
class StepNotifier:
    config: Config
    logger: logging.Logger
    last_message: str = ""

    def enabled_for_telegram(self) -> bool:
        return bool(
            self.config.notify_steps
            and self.config.telegram_bot_token.strip()
            and self.config.telegram_allowed_chat_id.strip()
        )

    def step(self, title: str, detail: str = "", *, telegram: bool = True, rule_key: str = "worker_step") -> None:
        message = f"[{datetime.now().strftime('%H:%M:%S')}] {title}"
        if detail:
            message = f"{message} - {detail}"

        self.last_message = message
        self.logger.info(message)
        print(message, flush=True)
        update_state(last_status=message, last_step=title)

        if telegram and self.enabled_for_telegram():
            allowed, reason = should_send(rule_key)
            if not allowed:
                if rule_key not in {"worker_step", "signal", "market_snapshot"}:
                    self.logger.info("Telegram notification skipped. rule=%s reason=%s", rule_key, reason)
                return
            self._send_telegram(message)

    def signal(self, action: str, reason: str, *, telegram: bool = True) -> None:
        action_text = korean_action(action)
        reason_text = korean_reason(reason)
        if action == "HOLD" and not self.config.notify_hold_signals:
            self.step("매매 신호", f"{action_text}: {reason_text}", telegram=False)
            return
        self.step("매매 신호", f"{action_text}: {reason_text}", telegram=telegram, rule_key="signal")

    def telegram(self, text: str, *, rule_key: str) -> None:
        self.logger.info("Telegram candidate. rule=%s text=%s", rule_key, text)
        if not self.enabled_for_telegram():
            return
        allowed, reason = should_send(rule_key)
        if not allowed:
            if rule_key not in {"worker_step", "signal", "market_snapshot"}:
                self.logger.info("Telegram notification skipped. rule=%s reason=%s", rule_key, reason)
            return
        self._send_telegram(text)

    def _send_telegram(self, text: str) -> None:
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.config.telegram_bot_token.strip()}/sendMessage",
                json={
                    "chat_id": self.config.telegram_allowed_chat_id.strip(),
                    "text": text,
                },
                timeout=5,
            ).raise_for_status()
        except Exception as exc:
            self.logger.warning("Telegram notification failed: %s", exc)

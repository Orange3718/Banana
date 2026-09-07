from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import requests

from config import Config
from notifier import korean_action, korean_reason
from runtime_state import RuntimeState, load_state, set_command
from settings_store import load_settings
from telegram_decision import (
    approve_recommendation,
    exclude_market,
    explain_recommendation,
    include_market,
    reject_recommendation,
    send_recommendations,
    set_group,
    set_mode,
    set_trading_style,
)


PROJECT_DIR = Path(__file__).resolve().parent
LOG_PATH = PROJECT_DIR / "logs" / "telegram_control.log"


def _api_url(token: str, method: str) -> str:
    return f"https://api.telegram.org/bot{token}/{method}"


def _format_status(state: RuntimeState) -> str:
    settings = load_settings()
    mode = "실행 중" if not state.paused and not state.kill_switch else "일시정지"
    if state.kill_switch:
        mode = "킬 스위치 작동 중"
    price = f"{state.last_price:,.0f} KRW" if state.last_price else "-"
    return (
        "업비트 자동매매 상태\n"
        f"- 모드: {mode}\n"
        f"- 운영 단계: {settings.mode_label}\n"
        f"- 거래 성향: {settings.style_label}\n"
        f"- 현재 단계: {state.last_step or '-'}\n"
        f"- 현재 상태: {state.last_status}\n"
        f"- 마켓: {state.last_market or '-'}\n"
        f"- 마지막 가격: {price}\n"
        f"- 마지막 신호: {korean_action(state.last_signal)}\n"
        f"- 신호 사유: {korean_reason(state.last_signal_reason) if state.last_signal_reason else '-'}\n"
        f"- 보유 수량: {state.position_volume:.8f}\n"
        f"- 사용 가능 KRW: {state.available_krw:,.0f}\n"
        f"- 손익률: {state.profit_rate:+.2%}\n"
        f"- 하트비트: {state.last_heartbeat or '-'}\n"
        f"- 모의거래: {state.dry_run}\n"
        f"- 실거래 허용: {state.real_trade_enabled}"
    )


def _help_text() -> str:
    return (
        "사용 가능한 명령\n"
        "/status - 현재 봇 상태 확인\n"
        "/recommend - 추천 코인 TOP 목록과 승인 요청 확인\n"
        "/why KRW-ETH - 특정 코인을 왜 추천했는지 확인\n"
        "/approve KRW-ETH - 승인형 실제 추천 매매 승인\n"
        "/reject KRW-ETH 사유 - 추천 거절과 사유 기록\n"
        "/watch KRW-SOL - 감시/추천 후보에 포함\n"
        "/exclude KRW-DOGE - 추천/매매 후보에서 제외\n"
        "/include KRW-DOGE - 제외 해제\n"
        "/group KRW-ETH major - 코인 그룹 변경\n"
        "/mode 1|2|3|4 - 운영 단계 변경\n"
        "/style conservative|balanced|aggressive - 거래 성향 변경\n"
        "/resume - 자동매매 루프 시작 또는 재개\n"
        "/pause - 자동매매 루프 일시정지\n"
        "/kill - 킬 스위치 작동\n"
        "/reset - 킬 스위치 해제 후 일시정지 유지\n"
        "/help - 도움말 보기"
    )


def _log_message(text: str) -> None:
    LOG_PATH.parent.mkdir(exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as file:
        file.write(text + "\n")


class TelegramControlBot:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.token = config.telegram_bot_token.strip()
        self.allowed_chat_id = config.telegram_allowed_chat_id.strip()
        self.offset = 0

    def enabled(self) -> bool:
        return bool(self.token)

    def send_message(self, chat_id: int | str, text: str) -> None:
        requests.post(
            _api_url(self.token, "sendMessage"),
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        ).raise_for_status()

    def get_updates(self) -> list[dict[str, Any]]:
        response = requests.get(
            _api_url(self.token, "getUpdates"),
            params={"timeout": 25, "offset": self.offset},
            timeout=35,
        )
        response.raise_for_status()
        payload = response.json()
        if not payload.get("ok"):
            raise RuntimeError(f"Telegram getUpdates failed: {payload}")
        return list(payload.get("result", []))

    def is_allowed(self, chat_id: int) -> bool:
        if not self.allowed_chat_id:
            return False
        return str(chat_id) == self.allowed_chat_id

    def handle_message(self, message: dict[str, Any]) -> None:
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        if chat_id is None:
            return

        text = str(message.get("text") or "").strip()
        _log_message(f"chat_id={chat_id} text={text}")
        if not self.allowed_chat_id:
            self.send_message(
                chat_id,
                f"현재 chat id는 {chat_id}입니다. .env에 TELEGRAM_ALLOWED_CHAT_ID={chat_id}를 입력한 뒤 다시 시작하세요.",
            )
            return
        if not self.is_allowed(int(chat_id)):
            self.send_message(chat_id, "허용되지 않은 채팅입니다.")
            return
        if not text:
            self.send_message(chat_id, "알 수 없는 명령입니다.\n\n" + _help_text())
            return

        parts = text.split()
        command = parts[0].lower()
        args = parts[1:]

        try:
            if command in {"/start", "/help"}:
                self.send_message(chat_id, _help_text())
            elif command == "/status":
                self.send_message(chat_id, _format_status(load_state()))
            elif command == "/recommend":
                send_recommendations(self.config, chat_id, self.send_message)
            elif command == "/why":
                self.send_message(chat_id, explain_recommendation(args[0].upper()) if args else "예: /why KRW-ETH")
            elif command == "/approve":
                self.send_message(chat_id, approve_recommendation(self.config, args[0].upper()) if args else "예: /approve KRW-ETH")
            elif command == "/reject":
                market = args[0].upper() if args else ""
                reason = " ".join(args[1:]) if len(args) > 1 else ""
                self.send_message(chat_id, reject_recommendation(market, reason) if market else "예: /reject KRW-ETH 과열이라 보류")
            elif command in {"/watch", "/include"}:
                self.send_message(chat_id, include_market(args[0].upper()) if args else "예: /include KRW-DOGE")
            elif command == "/exclude":
                self.send_message(chat_id, exclude_market(args[0].upper()) if args else "예: /exclude KRW-DOGE")
            elif command == "/group":
                self.send_message(chat_id, set_group(args[0].upper(), args[1]) if len(args) >= 2 else "예: /group KRW-ETH major")
            elif command == "/mode":
                self.send_message(chat_id, set_mode(args[0]) if args else "예: /mode 2")
            elif command == "/style":
                self.send_message(chat_id, set_trading_style(args[0]) if args else "예: /style aggressive")
            elif command == "/resume":
                set_command("resume", "telegram")
                self.send_message(chat_id, "자동매매 루프를 시작/재개했습니다.")
            elif command == "/pause":
                set_command("pause", "telegram")
                self.send_message(chat_id, "자동매매 루프를 일시정지했습니다.")
            elif command == "/kill":
                set_command("kill", "telegram")
                self.send_message(chat_id, "킬 스위치를 작동했습니다. 신규 주문 판단이 차단됩니다.")
            elif command == "/reset":
                set_command("reset", "telegram")
                self.send_message(chat_id, "킬 스위치를 해제했습니다. 봇은 일시정지 상태를 유지합니다.")
            else:
                self.send_message(chat_id, "알 수 없는 명령입니다.\n\n" + _help_text())
        except Exception as exc:
            self.send_message(chat_id, f"명령 처리 중 오류가 발생했습니다: {exc}")

    def run_forever(self) -> None:
        if not self.enabled():
            raise RuntimeError("TELEGRAM_BOT_TOKEN is empty. Set it in .env first.")

        print("텔레그램 제어 봇이 실행 중입니다.")
        while True:
            try:
                for update in self.get_updates():
                    self.offset = int(update["update_id"]) + 1
                    message = update.get("message") or update.get("edited_message")
                    if message:
                        self.handle_message(message)
            except KeyboardInterrupt:
                print("텔레그램 제어 봇이 중지되었습니다.")
                return
            except Exception as exc:
                print(f"텔레그램 봇 오류: {exc}")
                time.sleep(5)


def main() -> None:
    config = Config.load(PROJECT_DIR / ".env")
    TelegramControlBot(config).run_forever()


if __name__ == "__main__":
    main()

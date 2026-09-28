"""Read-only Kiwoom connection check. Places no orders.

Run on the machine that actually holds the real KIWOOM_APP_KEY /
KIWOOM_APP_SECRET in its local .env (never commit that file):

    cd upbit-auto-trader
    python tools/test_kiwoom_connection.py

It fetches an OAuth2 token and one account-balance snapshot, then prints
the raw response so you can confirm or correct the header/field
assumptions flagged as unverified in MULTI_ASSET_STOCK_DESIGN.md section
32.4 before relying on kiwoom_client.py for anything real.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Config
from kiwoom_client import KiwoomAPIError, KiwoomClient


def _mask(token: str) -> str:
    if len(token) <= 10:
        return "*" * len(token)
    return f"{token[:6]}...{token[-4:]} (len={len(token)})"


def main() -> int:
    project_dir = Path(__file__).resolve().parents[1]
    config = Config.load(project_dir / ".env")

    if not config.kiwoom_app_key or not config.kiwoom_app_secret:
        print(".env의 KIWOOM_APP_KEY / KIWOOM_APP_SECRET가 비어 있습니다. 먼저 채워주세요.")
        return 1

    print(f"base_url = {config.kiwoom_base_url}")
    if config.kiwoom_base_url.rstrip("/") == "https://api.kiwoom.com":
        print("경고: 실전 도메인입니다. 첫 연결 확인은 모의투자 도메인(mockapi.kiwoom.com)을 권장합니다.")

    client = KiwoomClient(
        app_key=config.kiwoom_app_key,
        app_secret=config.kiwoom_app_secret,
        account_no=config.kiwoom_account_no,
        base_url=config.kiwoom_base_url,
    )

    try:
        token = client._ensure_token()
    except KiwoomAPIError as exc:
        print(f"토큰 발급 실패: {exc}")
        return 1
    print(f"토큰 발급 성공: {_mask(token)}")

    try:
        balance = client.get_account_balance()
    except KiwoomAPIError as exc:
        print(f"계좌평가현황 조회 실패: {exc}")
        print("MULTI_ASSET_STOCK_DESIGN.md 32.4의 api-id 헤더/필드 가정이 틀렸을 수 있습니다.")
        return 1

    print("계좌평가현황 원본 응답 (필드명을 MULTI_ASSET_STOCK_DESIGN.md 32.4와 대조하세요):")
    print(balance)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

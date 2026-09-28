"""Kiwoom mock-trading order round-trip check. Refuses to run against the
production domain, no matter what .env says.

This places one small market buy, checks the resulting balance, then
market-sells the same quantity to return to flat. It exists to verify
kiwoom_client.py's order methods against a real (mock) response before
anyone considers pointing this code at real money.

Run on the machine that holds the real KIWOOM_APP_KEY / KIWOOM_APP_SECRET
in its local .env (never commit that file):

    cd upbit-auto-trader
    python tools/test_kiwoom_mock_order.py --stock-code 005930 --quantity 1
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from config import Config
from kiwoom_client import KiwoomAPIError, KiwoomClient

MOCK_HOST_MARKER = "mockapi.kiwoom.com"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock-code", required=True, help="예: 005930 (삼성전자)")
    parser.add_argument("--quantity", type=int, default=1, help="테스트 수량, 기본 1주")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_dir = Path(__file__).resolve().parents[1]
    config = Config.load(project_dir / ".env")

    if MOCK_HOST_MARKER not in config.kiwoom_base_url:
        print(
            f"거부: KIWOOM_BASE_URL이 모의투자 도메인({MOCK_HOST_MARKER})이 아닙니다 "
            f"(현재: {config.kiwoom_base_url}). 이 스크립트는 실전 도메인에서는 실행하지 않습니다."
        )
        return 1

    if not config.kiwoom_app_key or not config.kiwoom_app_secret:
        print(".env의 KIWOOM_APP_KEY / KIWOOM_APP_SECRET가 비어 있습니다. 먼저 채워주세요.")
        return 1

    print(f"base_url = {config.kiwoom_base_url} (모의투자 확인됨)")
    print(f"종목코드 = {args.stock_code}, 수량 = {args.quantity}")

    # 재시도 중 실주문이 중복 접수될 위험을 이 테스트에서부터 없애기 위해 1회로 고정한다.
    client = KiwoomClient(
        app_key=config.kiwoom_app_key,
        app_secret=config.kiwoom_app_secret,
        account_no=config.kiwoom_account_no,
        base_url=config.kiwoom_base_url,
        max_retries=1,
    )

    try:
        before = client.get_account_balance()
    except KiwoomAPIError as exc:
        print(f"매수 전 계좌조회 실패: {exc}")
        return 1
    print("매수 전 계좌평가현황:")
    print(before)

    input(f"\n{args.stock_code} {args.quantity}주 시장가 매수를 지금 접수합니다. Enter를 누르면 진행합니다 (Ctrl+C로 취소)... ")

    try:
        buy_result = client.market_buy(args.stock_code, args.quantity)
    except KiwoomAPIError as exc:
        print(f"매수 주문 실패: {exc}")
        return 1
    print("매수 주문 응답:")
    print(buy_result)

    time.sleep(2)
    try:
        after_buy = client.get_account_balance()
    except KiwoomAPIError as exc:
        print(f"매수 후 계좌조회 실패: {exc}")
        return 1
    print("매수 후 계좌평가현황 (수량·평가금액 필드명을 32.4와 대조하세요):")
    print(after_buy)

    input("\n확인했으면 Enter를 눌러 같은 수량을 시장가 매도해 포지션을 정리합니다 (Ctrl+C로 중단하고 수동 정리)... ")

    try:
        sell_result = client.market_sell(args.stock_code, args.quantity)
    except KiwoomAPIError as exc:
        print(f"매도 주문 실패: {exc}")
        print("포지션이 남아 있을 수 있습니다. 모의투자 화면에서 직접 확인하세요.")
        return 1
    print("매도 주문 응답:")
    print(sell_result)

    time.sleep(2)
    try:
        after_sell = client.get_account_balance()
    except KiwoomAPIError as exc:
        print(f"매도 후 계좌조회 실패: {exc}")
        return 1
    print("매도 후 계좌평가현황 (매수 전 수치와 비교해 포지션이 원복됐는지 확인):")
    print(after_sell)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

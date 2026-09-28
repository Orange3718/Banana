# Neural Trade 세션 인수인계

저장 시점: 2026-09-28 KST

현재 코드, 실제 운영 상태, 전략 설정, 검증 결과와 다음 작업은 저장소 루트의
[`docs/TRADING_HANDOFF_2026-09-28.md`](../docs/TRADING_HANDOFF_2026-09-28.md)에
통합했다. 새 컴퓨터나 새 세션에서는 해당 문서를 먼저 읽는다.

핵심 경계:

- `.env`, API 키, 거래 원장과 런타임 상태를 Git에 넣지 않는다.
- Upbit와 Binance 실주문 워커를 다른 컴퓨터에서 중복 실행하지 않는다.
- KRW와 USDT 손익을 합산하지 않는다.
- 사용자가 중단과 킬을 결정한다.
- 조회 대시보드와 수집기는 주문을 실행하지 않는다.

검증 시작 명령:

```bash
python -m pytest -q tests_next
python -m neural.preflight
```

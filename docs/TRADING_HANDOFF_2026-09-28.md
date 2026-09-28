# Upbit·Binance 거래 시스템 인수인계

기준 시각: 2026-09-28 08:10 KST

## 목적과 운영 경계

이 문서는 다른 컴퓨터나 새 작업 세션에서 현재 거래 시스템을 이어서 점검하고
개발하기 위한 단일 시작점이다. 실제 주문은 iMac의 독립 LaunchAgent가 담당하고,
대시보드 API는 조회와 런타임 제어 상태만 제공한다. 사용자가 중단과 킬을
결정하며 자동 점검이나 개발 작업은 실행 상태, 주문 크기, 레버리지 또는
포지션을 임의로 바꾸지 않는다.

- Upbit 현물과 Binance USD-M 선물의 손익과 잔고는 서로 합산하지 않는다.
- `.env`, 거래 원장, 런타임 상태와 API 키는 Git에 저장하지 않는다.
- 거래소 키에는 출금 권한을 부여하지 않고 허용 IP를 사용한다.
- 동일 거래소 실주문 워커를 두 컴퓨터에서 동시에 실행하지 않는다.

## Git 재개 지점

- 저장소: `git@github.com:Orange3718/Banana.git`
- 브랜치: `feat/trading-reliability-20260928`
- 프로젝트: `upbit-auto-trader/`
- 전략 근거:
  - `docs/UPBIT_STRATEGY_VALIDATION_2026-09-27.md`
  - `docs/BINANCE_STRATEGY_VALIDATION_2026-09-27.md`

```bash
git clone git@github.com:Orange3718/Banana.git
cd Banana
git switch feat/trading-reliability-20260928
cd upbit-auto-trader
cp .env.example .env
```

실제 `.env`는 기존 iMac의 로컬 파일을 보안 경로로 옮기거나 각 거래소에서 새
키를 발급해 작성한다. 채팅, PR, Git 커밋으로 전달하지 않는다.

## iMac 실제 운영 상태

2026-09-28 점검에서 다음 항목을 확인했다.

| 항목 | 상태 |
| --- | --- |
| Upbit 실주문 워커 | LaunchAgent 실행 중, `DRY_RUN=false`, `ENABLE_REAL_TRADE=true` |
| Binance 실주문 워커 | LaunchAgent 실행 중, 현재 포지션 0 |
| Upbit·Binance 수집기 | 각 30초 주기, `connected` |
| 조회 API | `http://127.0.0.1:8766`, 정상 |
| 원격 대시보드 | `https://orange-imac.tail14202a.ts.net:9443/` |
| 외부 감시 | Watchdog 5분 주기, 상태 전환 때만 알림 |

현재 배포 설정은 다음과 같다.

- Upbit: 추세 확인·추세 눌림목만 신규 진입, 1회 기준 50,000원,
  종목당 150,000원, 최대 5종목, 하루 최대 12회, 손절 2.5%,
  현금 예비 `max(30,000원, 평가금의 10%)`, 일일 손실·오픈 리스크 각 2%.
- Binance: `BTCUSDT,SOLUSDT` 롱 전용, 격리 1배, 목표 명목금액 550 USDT,
  24시간 돌파/청산 채널, 손절 2.5%, UTC 일일 손실 한도 30 USDT,
  진입 즉시 거래소 `STOP_MARKET` 보호 주문 확인.

실제 키와 활성화 값은 Git의 `.env.example`이 아니라 iMac 로컬 `.env`와
LaunchAgent 상태를 기준으로 확인한다.

## 마지막 성과 스냅샷

- Upbit: 9월 13일 이후 수수료 포함 FIFO 실현손익 `+4,240원`, 종료 154건,
  승률 58.4%. 최근 20건은 `-3,439원`, 손익계수 0.53이라 재검토 대상이다.
- Binance: 9월 13일 워커 시작 이후 수수료·펀딩비 포함 `+6.7089 USDT`,
  종료 111건. 최근 20건은 `+14.7750 USDT`, 손익계수 2.38이다.
- 위 누적값에는 과거 폐기한 전략이 포함된다. 현재 전략은 종료 표본이 20건보다
  적으므로 기대수익을 확정하지 않는다.

## 검증 명령과 결과

```bash
cd upbit-auto-trader
python -m pytest -q tests_next
python -m compileall -q .

cd apps/dashboard
pnpm install --frozen-lockfile
pnpm run build

cd ../../../
python -m unittest tools/test_ops_watchdog.py
```

2026-09-28 PR 작성 전 결과:

- 거래 테스트: 43개 통과
- Watchdog 테스트: 13개 통과
- Python 컴파일 및 `git diff --check`: 통과
- React/TypeScript/Vite 프로덕션 빌드: 통과
- 실운영 스모크 검사: DNS, Upbit·Binance 공개 API, 두 수집기, 로컬 API와
  Tailscale 대시보드가 모두 정상이고 로컬·원격 대시보드가 HTTP 200을 반환함

## 다음 실행 순서

1. PR에서 비밀정보와 런타임 산출물이 제외됐는지 확인한다.
2. 현재 전략으로 종료된 거래를 거래소 원장과 대조해 20건까지 축적한다.
3. Upbit 최근 20건 순손실의 전략별 원인을 새 설정 적용 전후로 분리한다.
4. Upbit의 미가격 자산 `CFI,TIX,LUNC,SGB,LUNA2,FLR,PURSE` 처리 정책을 정해
   전체 평가금이 `null`이 되는 문제를 해결한다.
5. Binance 포지션이 새로 열리면 격리 1배, 수량, 진입가, 단일 보호 주문을
   거래소 API와 즉시 대조한다.

현재 워커를 멈추거나 설정을 바꾸는 일은 이 인수인계 작업의 범위가 아니다.

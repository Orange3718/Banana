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

1. ~~PR에서 비밀정보와 런타임 산출물이 제외됐는지 확인한다.~~ 2026-09-28
   클라우드 세션에서 재확인 완료: PR #4 diff 94개 파일 중 실제 값이 들어있는
   것은 없고 `.env.example`만 포함되며 키·토큰은 모두 빈 값이다.
   `upbit-auto-trader/.gitignore`가 `.env`, `*.jsonl`, `*_state.json`,
   `logs/`, `artifacts/`를 이미 제외한다.
2. 현재 전략으로 종료된 거래를 거래소 원장과 대조해 20건까지 축적한다.
   (실거래소 접근과 iMac `.env`가 필요해 클라우드 세션에서는 수행 불가.)
3. Upbit 최근 20건 순손실의 전략별 원인을 새 설정 적용 전후로 분리한다.
   (실제 거래 원장이 Git에 없어 클라우드 세션에서는 수행 불가.)
4. ~~Upbit의 미가격 자산 `CFI,TIX,LUNC,SGB,LUNA2,FLR,PURSE` 처리 정책을 정해
   전체 평가금이 `null`이 되는 문제를 해결한다.~~ 2026-09-28 재검토 결과
   이미 의도된 정책으로 구현·테스트되어 있음을 확인했다: 가격을 확인할 수
   없는 자산이 하나라도 있으면 `neural/collector.py`의 `normalize()`가
   `equity`를 절대 0으로 대체하지 않고 `None`으로 두며(회귀 테스트
   `tests_next/test_service.py::test_unpriced_never_becomes_zero_equity`),
   `apps/dashboard/src/main.tsx`는 이때 `priced_subtotal`로 대체 표시하고
   카드 라벨을 "확인된 평가자산"으로 바꾸며 제외된 심볼을 배너로 알린다.
   위 7개 심볼은 Upbit KRW 마켓에서 영구 상장폐지된 자산이라 이 상태가
   일시적이 아니라 계속 유지되는 것이며, 결함이 아니다. Owner 확인: 이
   보수적인 표시 방식(0으로 위장하지 않고 확인된 금액만 보여주며 제외
   내역을 공개)을 그대로 유지하기로 했다. 델리스트 자산을 0원으로 강제
   반영하거나 대시보드에서 숨기는 방안은 채택하지 않는다.
5. Binance 포지션이 새로 열리면 격리 1배, 수량, 진입가, 단일 보호 주문을
   거래소 API와 즉시 대조한다.
   (실거래소 접근이 필요해 클라우드 세션에서는 수행 불가.)

현재 워커를 멈추거나 설정을 바꾸는 일은 이 인수인계 작업의 범위가 아니다.

## 2026-09-28 클라우드 세션 인수인계

이 문서의 "다음 실행 순서" 중 1번과 4번은 클라우드 세션(iMac `.env`·실거래소
접근 불가)에서 코드와 PR diff만으로 검증·확인 가능해 완료했다. 2·3·5번은
실거래소 원장, iMac 로컬 `.env`, 실행 중인 워커 상태가 있어야 하므로 iMac
로컬 세션이나 실거래소 접근이 가능한 환경에서 이어서 진행해야 한다.

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

## 2026-09-28 클라우드 세션 2차: 키움 초기 코드 + KR 전략 착수

같은 클라우드 세션에서 이어서 다음을 추가했다. 전부 PR #4 브랜치
(`feat/trading-reliability-20260928`)에 이미 fast-forward push됐다.

1. `kiwoom_client.py` — `upbit_client.py`와 같은 dataclass·재시도 구조의
   키움증권 REST 클라이언트 초기 코드(OAuth2 토큰, 계좌평가현황 `kt00004`,
   매수/매도/정정/취소 `kt10000`~`kt10003`). App Key/Secret이 없고 이
   세션은 `api.kiwoom.com`/`mockapi.kiwoom.com`에 네트워크로 닿지 못해
   실계좌 검증은 안 됐다 — 헤더명(`api-id`) 등은 추정치다
   (`MULTI_ASSET_STOCK_DESIGN.md` 32.4 참고).
2. `config.py`·`.env.example`에 `KIWOOM_*` 환경변수 추가. 기본값은 모의투자
   도메인과 `KIWOOM_DRY_RUN=true`, 키는 빈 값 — 기존 동작에 영향 없음.
3. `tools/test_kiwoom_connection.py` — 읽기 전용(토큰 발급 + 계좌조회만,
   주문 없음) 연결 확인 스크립트. 실제 키가 있는 로컬 기기에서만 실행한다.
4. `neural/kr_value_price_catalyst.py` — `MULTI_ASSET_STOCK_DESIGN.md` 17절
   "전략 C: 삼박자형"(가치 40·가격 35·재료 25)의 채점·진입·청산 로직을
   `neural/strategy_lab.py`와 같은 오프라인·무자격증명 원칙으로 구현했다.
   재료 점수는 정형 공시만 사용하고 원문 뉴스 헤드라인은 신호로 쓰지
   않는다(16절 원칙 유지). 이 세션은 KRX·DART·네이버금융도 네트워크
   정책상 전부 막혀 있어 **실제 종목 데이터로는 검증하지 못했고**, 합성
   입력값 테스트(`tests_next/test_kr_value_price_catalyst.py`, 18개)만
   통과했다. "이 조합이 실제로 돈을 번다"는 근거가 아니라 "설계 방향이
   학술적으로 타당하다"는 근거(강환국 퀀트 백테스트, 한국 시장 PEAD 논문,
   거래량-수익률 상관관계 KCI 논문)만 있다는 점을 다음 세션도 그대로
   유지해야 한다.
5. `python -m pytest -q tests_next` 61개 전부 통과(기존 43 + 신규 18),
   `python -m compileall -q .` 통과. 클린 venv에서 실행: 이 컨테이너는
   `requirements.txt`의 `ta` 패키지가 최신 setuptools와 충돌해 빌드
   실패하므로, 검증 시 `pip install "setuptools<66"`를 먼저 하거나
   `python -m venv`로 새 가상환경을 만들어야 한다.

### 맥에서 할 일 (지금 시점 기준)

- [ ] `git pull` — 이 절의 커밋들(키움 클라이언트, 연결 테스트 스크립트,
      KR 전략 모듈)을 받는다.
- [ ] `.env`에 `KIWOOM_APP_KEY`/`KIWOOM_APP_SECRET`/`KIWOOM_ACCOUNT_NO`를
      채운다 (키움에서 모의투자용으로 먼저 발급). **Git에는 절대 커밋하지
      않는다.**
- [ ] `python tools/test_kiwoom_connection.py` 실행 — 토큰 발급과 계좌조회
      원본 응답을 32.4의 가정과 대조하고, 다르면 `kiwoom_client.py`를
      맥에서 직접 고치거나 다음 세션에 그 응답을 알려준다.
- [ ] (여유가 되면) `pip install pykrx` 등으로 KOSPI/KOSDAQ 과거 시세와
      DART 공시를 받아 `neural/kr_value_price_catalyst.py`를 실제 데이터로
      백테스트한다. 이건 맥의 일반 인터넷이 필요하고, 이 클라우드 세션은
      할 수 없었던 부분이다.
- [ ] 기존 Upbit/Binance 실거래 워커·설정은 이 작업들과 무관하게 그대로
      둔다 (이번 작업들은 어떤 실행 워커에도 연결되지 않았다).

### Git 푸시 기준 — 여러 곳에서 한 프로젝트 다루는 법

혼동의 원인: 클라우드 세션은 매번 `feat/trading-reliability-20260928-<임의문자열>`
같은 세션 전용 브랜치를 자동으로 만든다. 그래서 "내가 어느 브랜치에
푸시해야 하지?"가 헷갈릴 수 있다. 실제 규칙은 하나뿐이다.

> **어디서 작업하든 진짜 작업 브랜치는 `feat/trading-reliability-20260928`
> 하나뿐이다.** 클라우드 세션 전용 브랜치 이름은 무시하고, 항상 이
> 브랜치를 pull하고 이 브랜치로 push한다.

```bash
git switch feat/trading-reliability-20260928
git pull origin feat/trading-reliability-20260928

# ...작업...

git add <바뀐 파일>
git commit -m "설명"
git push origin feat/trading-reliability-20260928
```

클라우드 세션이 자체 브랜치에 커밋했다면(이 세션이 그랬듯), 다음처럼 같은
브랜치로 강제 없이 fast-forward push하면 된다 — 이미 이번 세션 내내 이
방식으로 PR #4에 반영했다.

```bash
git push origin <클라우드-세션-브랜치>:feat/trading-reliability-20260928
```

**장소별 역할 분담 (이번 세션에서 확인된 사실 기준):**

| 장소 | 할 수 있는 것 | 할 수 없는 것 |
| --- | --- | --- |
| 클라우드 세션(여기) | 코드 작성, 테스트, 문서화, Git/GitHub 조작, 일반 웹 검색 | 키움·업비트·바이낸스·KRX·DART 등 거의 모든 외부 사이트 접속(egress 정책 차단), 실제 `.env`/키 취급, 라이브 워커 실행·재시작 |
| 맥(iMac) | 실제 네트워크 전부, `.env`/키 보관, 라이브 트레이딩 워커 실행, 실제 데이터 백테스트 | (기기 자체 제약은 없음 — 사람이 직접 조작) |

**공통 원칙:**

1. 항상 `.env`·키·거래 원장은 Git에 올리지 않는다 — 어느 장소에서도 예외
   없음. 프라이빗 저장소도 예외 아님(위 원칙은 이미 이 문서와
   `.gitignore`에 반영돼 있다).
2. 작업을 시작하기 전 항상 `git pull`, 끝내기 전 항상 `git commit && git push`.
   두 장소를 오갈 때 이 습관만 지키면 "어느 게 최신인지 모르겠다"는 문제가
   생기지 않는다.
3. 같은 거래소의 실주문 워커를 두 컴퓨터에서 동시에 실행하지 않는다(이미
   상단에 명시된 규칙).
4. 이 문서(`docs/TRADING_HANDOFF_2026-09-28.md`)를 항상 최신 상태로 갱신되는
   단일 기준점으로 삼는다 — 새 파일을 계속 만들지 않고, 여기에 날짜별
   섹션을 추가하는 방식으로 이어간다. `REMOTE_RUNBOOK_KO.md`는 최초
   설치·실행 절차(포트, launchd 등록 등) 전용이고, 이 문서는 "지금 무엇을
   했고 다음에 뭘 해야 하는가" 전용이다.

## 2026-09-28 맥 세션: 브랜치 합류 + 키움 대시보드 + 장세 조기경보

같은 날 맥 로컬 세션(`/Users/orange/Developer/Banana-atemoya-ops`, 실제 라이브
워커가 도는 위치)에서 이어서 다음을 했다.

1. **브랜치 합류**: 맥에 쌓여 있던 미푸시 14커밋+미커밋 변경(대시보드,
   Binance 리스크 로직 수정 등)을 클라우드 세션의 `feat/trading-reliability-20260928`
   (키움 클라이언트·KR 전략)와 병합. `neural/binance_live.py`는 충돌 없이
   자동 병합됨. 충돌 22개는 파일별로 검토해서 해소(설정 계열은 양쪽 다
   유지, 문서는 더 최신 쪽 채택). 병합 커밋을 `feat/trading-reliability-20260928`에
   fast-forward push함.
2. **키움 대시보드 추가**: 실전 키로 라이브 검증해서 정확한 요청 필드를
   확인한 뒤 `kiwoom_client.py`에 `get_top_change_rate`/`get_top_volume_today`
   (ka10027/ka10030, 순위정보)와 `get_order_book`(ka10004, 10호가) 추가.
   `neural/api.py`에 `/api/v1/kiwoom/rankings`(30초 캐시)·
   `/api/v1/kiwoom/orderbook`(3초 캐시, REST 폴링이라 진짜 웹소켓 실시간은
   아님) 추가. 대시보드에 "키움" 탭 신설(등락률/거래량 상위 + 종목코드
   입력 10단계 호가창). 이 컨테이너엔 node/pnpm이 없어서 Node.js LTS를
   공식 tarball로 `~/.local`에 직접 설치(sudo 없이)해서 `pnpm run build`까지
   완료·라이브 반영함. 키움은 여전히 계좌조회·시세조회만 가능하고 어떤
   실주문 워커에도 연결되지 않았다.
3. **Upbit 장세 조기경보 검증**: 실제 업비트 공개 API로 받은 6개월치
   1시간봉으로 EMA20-EMA60 격차 축소를 "약세장 조기경보" 후보로 백테스트.
   재현율 89%/정밀도 58%/평균 선행 8.3시간. 정밀도가 낮아 `allow_new_buys`는
   건드리지 않고 텔레그램 메시지에 참고용 경고 한 줄만 추가(`strategy_router.py`
   의 `momentum_warning` 필드). 상세: `docs/UPBIT_REGIME_EARLY_WARNING_2026-09-28.md`.
4. 위 세 가지 모두 `python -m pytest -q tests_next` 61개 통과, `compileall`
   정상 확인 후 배포했고, `upbit-worker`·`api` LaunchAgent 재시작 시마다
   기존 포지션·설정이 유실 없이 정상 인식되는지 로그로 직접 확인했다.
5. 9/28 손익 점검(실거래 원장 기준): Upbit 9/13~ 매도 159건 순 +1,936원
   (9/27 정식 FIFO 검증의 +6,377원과는 계산 방식이 달라 참고용 근사치),
   9/27 이후 -2,335원. Binance(거래소 income 원장, 정확) 9/13~ +11.56 USDT,
   9/27~ -8.76 USDT. 두 거래소 다 9/27 전략 재검증 이후 소폭 마이너스
   흐름 — 위 3번 조기경보 검증도 이 관찰에서 시작됐다.

### 다음 세션이 이어받을 것

- [ ] 장세 조기경보(`market_regime_warning`)를 `trade_history.jsonl`에 매
      사이클 기록하도록 이미 연결해뒀다. 몇 주 뒤 라이브 재현율·정밀도를
      백테스트 수치(89%/58%)와 대조해서, 정보용 유지/포지션 축소/완전 차단
      중 어느 쪽으로 갈지 결정한다.
- [x] 2026-09-29 키움 실계좌 잔고 0원 — 해결됨. 실제로 빈 계좌였을 뿐이고
      필드 해석은 맞았다. 30만원 입금 후 정상 표시 확인. 상세는 아래
      "2026-09-29" 절.
- [ ] 두 번째 실전 계좌(단타/중장기 분리 운영 목적) App Key/Secret 아직
      없음 — 받으면 `KIWOOM_SCALP_*`/`KIWOOM_SWING_*` 식으로 설정 스키마
      확장.
- [ ] 종목 추천(KR_VALUE_PRICE_CATALYST)은 여전히 실데이터 미연결 —
      DART는 사용자가 "아직 하지 말자"고 보류함.

## 2026-09-29 키움 실전 첫 주문 왕복 검증

Owner가 소액(30만원 입금) 실전 계좌로 직접 매수→매도 왕복을 요청해 진행했다.
읽기 전용(토큰·잔고·시세·호가)만 검증됐던 `kiwoom_client.py`의 주문 메서드가
**이날 처음으로 실제 주문을 냈다.**

- 시장가 매수(`market_buy`, `trde_tp=3`)가 `855056:매수증거금이 부족합니다.
  0주 매수가능`으로 거부됐다. 계좌엔 30만원이 있고 삼성전자는 27만원대였는데도
  거부됐다 — 키움 앱 자체는 "주문가능수량 1"로 표시했다(스크린샷으로 대조).
- 공식 GitHub 샘플(`Kiwoom-Securities/Kiwoom-REST-API`의
  `examples/국내주식/주문/buy_domestic_stock.py`)과 요청 바디를 필드 단위로
  대조해 완전히 일치함을 확인 — 요청 형식 문제가 아니었다.
- 원인으로 추정한 것: **시장가 매수는 상한가(현재가 대비 +30%선) 기준으로
  증거금을 계산**하는 것으로 보인다. 지정가(`limit_buy`, `trde_tp=0`,
  `ord_uv=275000`)로 바꿔 재시도하니 즉시 체결됐다(`ord_no=0333071`,
  274,750원 체결). 시장가 매도(`market_sell`)는 같은 문제 없이 정상
  체결됐다(`ord_no=0333499`).
- 매수→매도 왕복 후 보유수량 0, 예수금 300,000원으로 원복 확인.
- `kiwoom_client.py` 클래스 docstring에 이 검증 결과와 "시장가 매수 대신
  지정가 권장" 가이드를 기록했다.

**결론**: 주문 실행 코드 자체는 정상 동작한다. 실거래 워커에 연결할 때는
반드시 `limit_buy`를 쓰거나, `market_buy`를 쓴다면 주문금액의 약 1.3배
현금 여유를 확인해야 한다. 이 문서 상단의 "kiwoom_client.py has no order
execution wired into any live worker yet" 상태는 아직 그대로다 — 오늘 한
건 완전히 수동 스크립트로 낸 테스트 주문이며, 자동 전략에는 여전히
연결되지 않았다.

# 거래 자동화·Telegram·n8n 전체 점검

기준일: 2026-09-07 KST

## 판정

전체 재설계가 필요한 상태는 아니다. 다만 회사 운영과 개인 매매가 같은 저장소·같은 iMac 안에서 섞여 있고, Telegram 수신 경로와 실제 주문 경로가 서로 다른 세대의 코드에 나뉘어 있어 **경계 정리와 운영 경로 단일화가 우선**이다.

## 확인된 실제 상태

| 영역 | 판정 | 확인 결과 |
| --- | --- | --- |
| Atemoya 핵심 인프라 | GOOD | PostgreSQL, n8n, webhook proxy가 실행 중이고 n8n health가 정상이다. |
| Atemoya Telegram 수신 | REVIEW | 활성 `telegramTrigger`는 1개이며 `AtemoyaTelegramMemory01`이다. 다른 Telegram 트리거는 비활성이다. |
| 개인 Upbit 주문 | GOOD | `com.orange3718.upbit-auto-trader.upbit-worker`가 실행 중이고 `DRY_RUN=false`, `ENABLE_REAL_TRADE=true` 상태다. |
| 개인 Upbit Telegram 발송 | REVIEW | 워커의 직접 발송 코드는 있으나 발송 실패를 주문 경로와 분리해 재처리하는 outbox가 없다. |
| 개인 Telegram 명령 수신 | BAD | `telegram_bot.py`는 존재하지만 LaunchAgent로 등록되어 있지 않아 `/status`, `/pause`, `/kill` 등 로컬 명령을 백그라운드에서 받지 않는다. |
| Binance | REVIEW | API 키와 계좌 조회 연결은 확인되지만 읽기·모의운용 경로만 실행된다. 실주문 실행기, 보호주문, 펀딩비·대사 경로는 준비되지 않았다. |
| n8n 최근 실행 | REVIEW | Gemini 수요초과, SQL 실패, Telegram parse entities 오류, DNS 오류 이력이 남아 있다. 전체 재설계보다 해당 노드의 fallback·쿼리·메시지 escape·재시도 정책을 고치는 편이 맞다. |
| 구형 Atemoya LaunchAgent | BAD | `command-center`는 없는 스크립트를 호출해 exit 127을 반복하고, `trend-radar`도 없는 파일로 exit 2를 반복한다. |

## 운영 경계

### 회사 Atemoya

```text
공개 자료 수집 -> PostgreSQL 근거 저장 -> Ollama/n8n 분석 -> QA
-> Telegram 회사 알림·승인 -> 게시 -> URL·성과 기록
```

### 개인 매매

```text
거래소 시세·계좌 -> 개인 전략 -> 개인 위험 게이트
-> 거래소별 주문 워커 -> 체결 대사·손익 원장 -> 개인 대시보드/Telegram
```

통합할 것은 상태 조회 방식, 서비스 생존 점검, 이벤트 형식, 읽기 전용 대시보드 투영뿐이다. API 키, 주문 큐, 위험 한도, 손익 원장, Telegram 봇·채팅, 회사 n8n 업무 데이터는 분리한다. 개인 매매를 Atemoya n8n의 주문 노드에 넣지 않는다.

## Telegram 정의

1. 회사용 Telegram은 `AtemoyaTelegramMemory01` 하나만 수신자로 유지한다. 승인·보류·거절·운영 질의는 회사 DB의 허용된 읽기 뷰와 결정 검증을 통과한다.
2. 개인용 Telegram은 별도 봇과 별도 chat id를 사용한다. `/status`, `/pause`, `/resume`, `/kill`, `/reset`은 개인 워커 제어용이다.
3. 개인 매매 알림은 체결·거부·위험·서비스 장애·일일 요약만 보낸다. 반복 HOLD와 정상 heartbeat는 기본 발송하지 않는다.
4. 같은 봇 토큰을 n8n 웹훅과 로컬 `getUpdates` 폴링에 동시에 연결하지 않는다. 개인 명령 수신기를 켜려면 전용 봇 토큰이 필요하다.
5. 주문 명령은 Telegram 문장만으로 실행하지 않는다. 허용 chat id, 명령 중복 키, 현재 설정 버전, 위험 게이트를 모두 검사한다.

## n8n 재설계 판단

전체 워크플로를 다시 만드는 대신 다음 세 묶음으로 정리한다.

### 유지

- `AtemoyaTelegramMemory01`: 유일한 inbound Telegram router
- Revenue Autopilot, Ops Guardian, Affiliate Health 등 회사 수익 운영 워크플로
- PostgreSQL safe query catalog와 감사 로그

### 수정

- Telegram 메시지는 Markdown/HTML을 명시적으로 escape하고 긴 메시지는 분할한다.
- SQL 노드는 컬럼·조인 검증을 먼저 수행하고 실패 시 빈 결과가 아니라 `REVIEW`를 기록한다.
- Gemini 실패 시 로컬 Ollama fallback과 재시도 간격을 적용한다.
- DNS·Telegram 전송 실패는 중앙 오류 기록과 지수 백오프를 사용하고, 같은 사건은 한 번만 알린다.
- 모든 활성 워크플로의 소유자, 실행 주기, 성공 조건, 실패 알림, 중복 키를 운영 표에 기록한다.

### 분리

- 개인 거래는 n8n의 업무·게시·승인 흐름과 분리한다.
- 개인 Telegram 제어는 n8n Telegram router에 합치지 않는다.
- Binance 실주문은 읽기 수집기와 별도 프로세스·별도 위험 게이트로 구현한다.

## 우선순위 개선안

1. 구형 `command-center`와 `trend-radar` LaunchAgent를 중지해 없는 경로의 재시작 소음을 없앤다.
2. 개인 Telegram은 전용 봇 토큰을 확보한 뒤 LaunchAgent로 등록하고, `/status`와 `/kill`만 먼저 실기능 검증한다.
3. Upbit 체결·수수료·손익을 개인 원장에 저장하고 Telegram 발송은 outbox 재시도와 연결한다.
4. Binance 모의운용에 실제 수수료·펀딩비·계약 단위·청산 위험을 반영한다.
5. 24시간 모의운용 후에도 Binance는 1배·최소 금액·보호주문 확인을 거친 별도 전환으로 둔다.
6. 개인 매매 코드를 별도 private 저장소와 별도 DB로 옮긴다.

## 이번 점검에서 하지 않은 것

- Upbit 주문 설정 변경 및 신규 주문 실행
- Binance 실주문 실행기 활성화
- API 키·Telegram 토큰 출력 또는 변경
- n8n 전체 재import·삭제

실주문 가능 여부와 수익률은 이 점검으로 보증되지 않는다. 현재 확인된 것은 프로세스 생존, 연결·수신 경로, 주문 경로의 분리 상태다.

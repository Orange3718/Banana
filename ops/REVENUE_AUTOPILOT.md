# Atemoya Revenue Autopilot

## 목적

대화가 열려 있지 않아도 공개 근거 수집부터 로컬 초안, QA, 승인 요청,
feature branch 게시 준비, 공개 URL 감지까지 이어간다. 외부 공개는 Owner의
Telegram 승인과 GitHub PR 병합을 통과해야 한다.

## 상시 흐름

1. `com.atemoya.source-scout`가 매시간 공개 자료를 수집한다.
2. `com.atemoya.local-llm`이 로컬 Ollama `qwen3.5:4b`로 근거 제한 분석을 저장한다.
3. n8n `AtemoyaRevenueAutopilot01`이 30분마다 후보를 중복 제거하고 하루 최대
   한 건의 장문 초안을 만든다.
4. 본문 길이, 근거 URL, 위험 HTML, 과장 표현을 자동 검사한다. 실패는 한 시간
   뒤 최대 세 번 재시도한다.
5. 통과한 초안은 PostgreSQL `content`, `approval_requests`,
   `revenue_autopilot_jobs`에 저장하고 Telegram으로 한 번만 승인 요청한다.
6. `/승인 <결정번호> 게시`가 기록되면 `com.atemoya.autopilot-publisher`가
   15분 안에 HTML과 sitemap을 생성·검증하고 feature branch에 커밋·push한다.
7. Publisher는 GitHub 비교 링크를 알린다. PR을 `main`에 병합한 뒤 공개 URL이
   HTTP 200이 되면 `published`로 기록하고 최종 URL을 한 번 알린다.
8. `com.atemoya.revenue-reconciler`가 15분마다 승인 상태와 작업 상태를 맞추고,
   승인 완료 작업은 Publisher를 즉시 깨우며 후보만 남은 경우 n8n을 다시 호출한다.

## 안전 기준

- 비밀값과 n8n credential은 파일·Git·Telegram에 기록하지 않는다.
- 직접 `main`에 쓰거나 자동 병합하지 않는다.
- 게시 전 Owner 승인, 결제·광고·인증은 별도 승인이다.
- Publisher는 feature branch가 아니거나 Git stage가 이미 사용 중이면 멈춘다.
- 동일 후보는 `local-run:<id>` 키, 동시 승인 요청은 DB 고유 인덱스로 막는다.
- 수익 후보는 구매·가격·비교·제품·제휴·쇼핑 의도가 확인된 근거만 사용한다.

## 사업 SLA

- 후보가 있지만 최근 7일 게시가 없으면 `REVIEW`다.
- 진행 가능한 작업이 72시간 이상 정체되면 `BAD`다.
- 승인 완료 작업이 45분 이상 Publisher로 넘어가지 않으면 `BAD`다.
- 서버가 정상이어도 게시·유입·클릭이 없으면 `GOOD`으로 판정하지 않는다.
- 조회·외부 클릭·제휴 클릭·전환·수익은 `revenue_channel_metrics`에 날짜와
  출처별로 보관한다. 실제 GA4 값은 Google Analytics Data API 인증 이후 수집한다.

## 운영 증거

- 대시보드: `http://100.102.120.59:8765/atemoya-dashboard.html`
- DB: `revenue_autopilot_jobs.stage`
- n8n: 30분 Schedule과 최근 실행
- Publisher: `/tmp/atemoya-autopilot-publisher.out`, `.err`
- Reconciler: `/tmp/atemoya-revenue-reconciler.out`, `.err`
- 공개 결과: `https://orange3718.github.io/Banana/autopilot/`

## 복구

워크플로 오류는 기존 `AtemoyaErrorHandler01`이 기록·보고한다. Publisher 실패는
한 시간 뒤 최대 세 번 재시도한다. DB와 n8n 복구는 `ops/BACKUP_RESTORE.md`를
따르며 생성 파일은 Git 이력에서 복구한다.

## 설치와 갱신

feature branch에서 `./ops/scripts/install-revenue-ops.sh`를 실행한다. 스크립트는
DB·n8n 백업, additive migration, 두 workflow import/publish, Reconciler
LaunchAgent 등록, n8n 재시작과 전체 검증을 순서대로 수행한다.

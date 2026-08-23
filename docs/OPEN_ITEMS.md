# Atemoya 미결 작업 정리

기준일: 2026-08-23

## 2026-08-23 현재 상태

최근 자동 점검: 2026-08-23 09:25 KST

운영 대시보드: `http://127.0.0.1:8765/atemoya-dashboard.html` (iMac), Tailscale 연결 시 `http://100.102.120.59:8765/atemoya-dashboard.html`. 메모리·예약 작업·현재/최근 로컬 실행·최근 수집 근거를 5초마다 읽는다. `GET /api/status`가 라이브 원천이며, PostgreSQL과 macOS 상태를 함께 표시한다.

- Git worktree: clean, branch `feat/atemoya-ops-baseline`
- n8n health: `{"status":"ok"}`
- Ollama: `qwen3.5:4b` 응답 가능
- 최근 로컬 LLM 실행: 09:25 종료, 최근 24시간 완료 49건·정리 오류 5건
- 최근 소스 수집: 3채널·20항목·로컬 분석 완료

### 실제 상시 운영

- `com.atemoya.local-llm`: 매시간 로컬 `qwen3.5:4b` 조사·콘텐츠 보조 2개 실행, PostgreSQL 기록, 중복 Telegram 억제
- `com.atemoya.source-scout`: 매시간 Hacker News·Reddit·Google News 공개 자료 수집, `source_observations` 저장, 로컬 분석
- `com.atemoya.nightly-reflection`: 매일 03:00 KST 최근 24시간 반추와 Telegram 보고
- `com.atemoya.local-llm-status`: 로컬 상태판 상시 제공
- n8n·PostgreSQL·Ollama: 2026-08-23 사전 점검 정상

예약 작업은 실행 사이에 `launchctl state = not running`으로 보이는 것이 정상이다. 등록 여부, `runs`, 최근 로그와 DB 실행시각을 함께 확인한다.

### 계정·채널 상태

- Telegram: n8n credential 연결 및 로컬 완료 Webhook 동작
- Coupang Partners: 로그인 세션 확인, LED 마스크 추적 링크 `https://link.coupang.com/a/grbrDLnnlA` 생성
- Gemini: n8n 암호화 credential 보존, 무료 범위 보조
- 네이버 블로그: 초안은 있으나 정식 자동 게시·성과 회수는 미완료
- Google Blogger/YouTube/GA4: 게시·측정 OAuth 전체 흐름 미완료

### 다음 우선순위

1. Telegram `GOOD / BAD / 수정` 답장을 게시 승인 상태와 연결
2. 근거 URL이 포함된 초안만 승인 요청하도록 QA 강화
3. GOOD 승인 후 GitHub Pages 게시와 게시 URL 저장을 먼저 완성
4. 네이버·Blogger OAuth 게시를 각각 연결하고 실제 게시 URL까지 검증
5. GA4·제휴 클릭·구매 신호를 콘텐츠별로 회수
6. 로컬 이미지 모델은 MLX 런타임만 설치됨. FLUX/SDXL 가중치·썸네일 생성·품질 검증은 미완료

### 반복 질문 방지

- 저장소의 `AGENTS.md`가 `.codex/skills/atemoya-operate/SKILL.md` 사용을 강제한다.
- 새 작업은 스킬의 preflight와 이 문서를 먼저 읽고 실제 다음 미결 작업을 진행한다.
- 백그라운드에 등록하지 않은 작업을 `진행 중`이라고 말하지 않는다.

## 최우선 운영 기준

자동화 구축보다 실제 수익화를 우선한다. 사례 조사 → 유입 → 페이지 체류 → 제휴 클릭 → 구매 가능성의 순서로 판단하고, 자동화는 이 과정을 반복·기록하는 보조 수단으로만 유지한다.

## 자동 진행 중

- **유입·수익화 운영**: 6시간마다 소셜 후보 조사, 검색형 페이지 개선, 성과 확인
- **제휴 페이지 건강 점검**: 매일 09:30 KST, 페이지·고지·제휴 링크·GA4 확인
- **커머스 스카우트**: 매주 월요일, 로컬 Qwen 3.5 4B로 후보 조사 후 PostgreSQL·Telegram 기록
- **GA4 데이터 축적**: 인위적인 방문·클릭 없이 실제 유입을 7일 이상 수집

## 현재 산출물

- LED 마스크 비교 페이지 공개
- LED 마스크 매일 사용 질문 페이지 공개
- Coupang Partners 추적 링크 연결
- 로컬 생성 세로 MP4 2종 보관

## 미결·차단

1. **Search Console 색인 요청** — Atemoya 소유 Google 계정 권한 필요
2. **실제 유입 데이터 확보** — 검색·SNS 배포 후 7일 관찰 필요
3. **두 번째 상품군 선정** — 소셜 신호와 클릭 데이터를 비교해 자동 선정
4. **Coupang 정산 정보** — 누적 수익 기준 충족 후 사용자 직접 입력

## 보류

- 첫 유료 n8n 번들: 범위·지원 제외 승인 전
- Mac Studio 구매·비용 기준: 실제 구매 계획 확정 전
- 위탁 공급사 연동: 공급·재고·배송 데이터 형식 확보 전

## 운영 원칙

사용자에게 매번 진행 승인을 묻지 않는다. 비밀번호·2FA·결제·법적 동의처럼 직접 입력이 필요한 항목만 알린다. 나머지는 자동화가 수행하고 결과만 보고한다.

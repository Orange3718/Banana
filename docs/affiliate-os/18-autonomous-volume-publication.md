# 18. 승인 없는 쿠팡 수량 확대 운영 설계와 구축 기록

갱신: 2026-09-14 09:20 KST
상태: **LIVE — 10건 대기열 중 1건 공개 검증 완료, 9건 예약**

## 결론

쿠팡 글이 늘지 않았던 직접 원인은 콘텐츠 부족이 아니라 **실행 경로 불일치**였다. 사용자 지시는 직접 게시였지만 운영 중인 n8n은 해외 커머스 뉴스 초안을 `approval_requests`에 넣었고, 실제 쿠팡 글 10건은 별도 수동 배포였다. 대기열 증가와 쿠팡 게시량 증가가 서로 연결되지 않았다.

이번 구축에서 두 경로를 분리했다.

- 레거시 `AtemoyaRevenueAutopilot01`: 신규 승인 요청을 만들지 않도록 비활성화했다. 진행 가능 상태였던 24건은 `rejected`, 미결 승인 5건은 `deferred`로 이력 보존했고 삭제하지 않았다.
- 신규 `com.atemoya.affiliate-direct-publisher`: 검토된 쿠팡 링크·원고·시각만 처리한다. 사람 승인과 모델 호출은 없다.
- PostgreSQL `affiliate.jobs`와 `affiliate.publications`: 예약, 시도, 해시, 권한 방식, 공개 URL과 검증 시각의 단일 실행 원장이다.
- 수량: 추가 10건, 하루 최대 3건. 첫 글은 2026-09-14 09:00 KST 공개 검증 완료했다.

## 왜 사용자가 같은 질문을 계속했는가

사용자는 단순히 원인을 궁금해한 것이 아니다. “다음 게시는 언제인가”, “왜 안 되고 있었나”, “다시”라는 질문으로 담당 AI가 운영 책임을 실제로 가져갔는지 확인하고 있었다. 이전 답변은 파일·링크·한 번의 배포는 보여 줬지만 다음 사건의 시각, 실행 주체, 실패 시 행동과 조회 위치를 하나로 연결하지 못했다. 그 빈칸을 사용자가 반복 질문으로 복구해야 했다.

이번에는 질문에 말로 답하는 대신 다음 상태를 기계가 보이게 만들었다.

1. 다음 게시 시각은 DB `next_attempt_at`과 manifest `scheduled_at`에 저장한다.
2. 예약 실행기는 15분마다 확인하고, 기한이 된 한 건만 점유한다.
3. 공개 성공은 Git push가 아니라 공개 URL의 HTTP 200, 제목, 제휴 링크와 고지 문구까지 확인해야 성립한다. 소스 해시는 Pages CI가 주입하는 Google/Naver 사이트 소유권 meta만 정규화한 뒤 비교한다.
4. 대시보드에 전체 10건의 예약·진행·공개·실패와 다음 시각을 표시한다.
5. 45분 넘게 기한을 초과하거나 수동 검토 상태가 하나라도 생기면 Watchdog이 `BAD`로 판단하고 Publisher를 한 번 깨운다.

## 실행 구조

```text
검토된 10건 JSON manifest
        │  링크·수량·본문·일정 QA
        ▼
PostgreSQL affiliate.jobs / publications
        │  direct_user_instruction · 하루 3건 상한 · SKIP LOCKED
        ▼
macOS LaunchAgent (15분 주기)
        │  아티팩트 해시 재검증
        ▼
격리된 detached Git worktree
        │  공개 allowlist·사이트·분석 스크립트 테스트
        ▼
origin/main → GitHub Pages
        │  HTTP 200 + 제목 + 고지 + 제휴 링크 검증
        ▼
published 상태·commit·URL·검증시각 → 대시보드 / Watchdog
```

개발 worktree의 Upbit 변경이나 이미 stage된 파일은 게시 커밋에 들어갈 수 없다. Publisher는 `/Users/orange/Atemoya/runtime/banana-public` 격리 worktree에서 `offers/<slug>.html`, `offers/index.html`, `sitemap.xml` 세 경로만 stage한다.

## 예약된 추가 10건

| 예약 KST | 카테고리 | 글 | 상태 |
|---|---|---|---|
| 09-14 09:00 | 뷰티 | LED 마스크 첫 2주 사용 루틴 | 공개 완료 |
| 09-14 14:00 | 주방 | 밀프렙 밀폐용기 수량·크기 | 예약 |
| 09-14 20:00 | 생활가전 | 로봇청소기 집 동선 실측 | 예약 |
| 09-15 09:00 | 운동 | 요가매트 두께·방 크기 | 예약 |
| 09-15 14:00 | 반려동물 | 자동급식기 정전·막힘 대응 | 예약 |
| 09-15 20:00 | 육아 | 물티슈 집·외출 보관 | 예약 |
| 09-16 09:00 | 여행 | 기내용 압축 파우치 배치 | 예약 |
| 09-16 14:00 | 사무 | 거치대·키보드 책상 배치 | 예약 |
| 09-16 20:00 | 계절가전 | 가열식 가습기 세척 시간 | 예약 |
| 09-17 09:00 | 전자기기 | 골전도 이어폰 출퇴근 착용 | 예약 |

각 글은 기존 글의 문장만 바꾼 복제가 아니라 서로 다른 사용 문제를 해결한다. 상품 선택을 새로 자동화하지 않았고, 2026-09-14 쿠팡 파트너스 도구에서 확인한 기존 10개 상품·링크 binding만 재사용했다. 자체 제휴 링크를 검증 목적으로 클릭하지 않는다.

## 자동 승인 의미

“승인을 AI가 한다”는 지시는 사람 확인을 다시 받지 말라는 운영 위임으로 구현했다. 콘텐츠를 무조건 통과시키는 의미로 해석하지 않았다.

| 사람 승인 | 기술 승인 |
|---|---|
| 없음. Telegram `GOOD/BAD`, PR 병합, 게시 확인 요청 없음 | 대상·권한·상품/링크 binding·본문 길이·금지 표현·정확한 고지·추적키·canonical·아티팩트 해시·공개 경계 검사 |

DB에는 모든 신규 publication을 `approval_id=NULL`, `authorization_mode=direct_user_instruction`으로 저장한다. 링크나 본문이 manifest와 달라지면 자동 승인하지 않고 `manual_review`로 바꾸며 뒤의 9건도 멈춘다.

## 수량을 하루 3건으로 정한 근거

- 한 번에 10건을 공개하면 어떤 글이 색인·조회·클릭을 만들었는지 배치 효과와 분리하기 어렵다.
- 3건이면 오전·오후·저녁의 실행과 공개 검증을 같은 날 관찰하면서도 실패가 전체 사이트로 확산되는 시간을 제한할 수 있다.
- 현재 수익은 0이고 외부 자연 유입 데이터도 연결되지 않았다. 따라서 더 많은 수량이 곧 매출이라는 근거는 없다.
- 추가 10건 뒤에는 자동으로 새 상품을 발굴하거나 같은 링크로 글을 더 복제하지 않는다. 다음 배치는 실제 조회·쿠팡 클릭/판매 데이터와 호스트 결정 뒤 다시 설계한다.

## 호스팅 결정과 제한

현재 사이트는 GitHub Pages다. GitHub 문서는 Pages를 온라인 사업·전자상거래나 상업 거래 촉진을 주목적으로 한 무료 호스팅으로 사용하는 것을 허용하지 않는다고 명시한다. 전체 Atemoya 사이트에는 비상업 계산기와 가이드도 있지만 제휴 비중을 계속 높이면 적합성 위험이 커진다.

- 결정: 이번 추가 10건을 **기존 링크의 제한된 편집 파일럿 상한**으로 둔다.
- 금지: 유료 유입, 결제 기능, 무제한 양산, 제휴 링크만 있는 얇은 페이지.
- 다음 배치 전 필수: 상업 콘텐츠를 허용하는 운영 호스트와 자체 도메인 ADR 확정.
- 근거: [GitHub Pages limits](https://docs.github.com/en/enterprise-cloud@latest/pages/getting-started-with-github-pages/github-pages-limits).

## 실패·재시도·중단

| 상황 | 처리 |
|---|---|
| 아직 예약 전 또는 오늘 3건 완료 | 정상 idle, 다음 예약 유지 |
| 네트워크·GitHub 일시 실패 | 1시간 뒤 같은 idempotency key로 재시도, 최대 3회 |
| push 성공·Pages 반영 지연 | 새 커밋을 만들지 않고 15분 뒤 공개 URL만 다시 확인 |
| 링크/해시/고지/경로 변조 | 즉시 `manual_review`, 후속 배치 정지 |
| 실행 lease 12분 만료 | 다음 실행에서 회수, 최대 시도 초과 시 정지 |
| 게시 예정 45분 초과 | Watchdog `BAD`, Publisher 한 번 재기동 |

## 실제 구축·검증 증거

- 설치·재검증 백업: `/Users/orange/Atemoya/backups/20260913T235613Z`, `/Users/orange/Atemoya/backups/20260913T235720Z`, `/Users/orange/Atemoya/backups/20260914T001323Z`.
- 레거시 격리 직전 백업: `/Users/orange/Atemoya/backups/20260914T000846Z`; 적용 후 pending approval 0, legacy stage는 published 1/rejected 117.
- DB: migration 014 적용, direct queue 10건과 immutable revision/link/publication binding 저장.
- 정적·회귀 테스트: Publisher 9건, 전체 Python 53건, 공개 산출물 Node 11건, affiliate inventory·site 검사 PASS.
- Watchdog: 미래 예약 정상, 45분 정체 BAD, manual review BAD를 포함한 회귀 검증 PASS.
- 첫 공개 commit: `356164df0074d557789c52fc881502095ed075cd`.
- 첫 Pages 실행: `34791301806`, completed/success.
- 전역 tracking 검사 배포 commit: `6ae3d89f1e352d14912aa148b16143ca4df1c2ef`; Pages 실행 `34791632103`, completed/success.
- 첫 공개 URL: `https://orange3718.github.io/Banana/offers/led-mask-first-two-weeks-routine.html`.
- 공개 검증: HTTP 200, 예상 제목·`g0MPccSO4q` 링크·정확한 쿠팡 고지 문구 확인.
- 운영 상태: legacy n8n workflow `active=false`; direct LaunchAgent 등록, 마지막 종료 코드 0.

## 사용자가 해야 하는 일

현재 10건 게시에는 없다. 로그인, 승인 답장, 링크 생성, PR 병합을 요구하지 않는다. 사용자가 개입할 상황은 다음 둘뿐이다.

1. 루프를 중단하고 싶을 때 운영 대시보드에서 확인 후 중단을 지시한다.
2. 다음 10건을 넘어 확대하기 전에 상업 호스트/도메인 선택처럼 소유자 결정이 필요한 새 범위가 생겼을 때 결정한다.

쿠팡 파트너스 최종 승인은 정상 외부 누적 판매가 기준에 도달한 뒤 채널 심사를 거쳐야 하며, 현재 매출 0원에서는 AI가 포털의 자격 조건을 우회해 승인할 수 없다. 이번 자동 승인은 **우리 게시 파이프라인 승인**이지 쿠팡 계정의 최종 승인을 대신하는 것이 아니다.

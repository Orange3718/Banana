# 11. 실행 상태·다음 작업 — 단일 재개 입구

갱신: 2026-09-14 20:50 KST
전체 판정: **REVIEW — 쿠팡 직접 게시 3/10 공개·7건 예약, 네이버 첫 게시 인증 대기, 유입·수익 효과는 아직 미검증**

## 현재 사용자 지시

- 소유한 쿠팡 제휴 콘텐츠의 검토·게시·운영은 AI가 직접 수행한다.
- 반복적인 승인, PR 병합, 계정 재연결을 사용자에게 요구하지 않는다.
- 사용자는 운영 루프를 중단하거나 새 지출·계정 보안·법적 동의·호스트 선택처럼 본인 결정이 필요한 경우에만 개입한다.
- Upbit와 영상 작업 변경은 별도 범위다. 이번 커밋·배포에 포함하지 않는다.

## 지금 실제로 동작하는 것

| 항목 | 상태 | 확인 증거 |
|---|---|---|
| 쿠팡 직접 게시 대기열 | LIVE | `affiliate.jobs`·`affiliate.publications` 10건, 모두 `direct_user_instruction` |
| 오늘 추가 글 | PUBLISHED 3 | 09:00 LED `356164d`, 14:00 밀폐용기 `19562a5`, 20:00 로봇청소기 `c5e3898`; 세 공개 URL 모두 publisher 검증 완료 |
| 남은 추가 글 | SCHEDULED 7 | 09-15 3건, 09-16 3건, 09-17 09:00 |
| 네이버 블로그 첫 글 | LOGIN BLOCKED | LED 마스크용 별도 원고 QA 완료. Chrome에 QR 로그인 화면을 열었으며 활성·저장 세션이 없어 사용자 앱 스캔 1회가 필요 |
| 실행기 | LIVE | `com.atemoya.affiliate-direct-publisher`, 15분 간격, 최근 exit 0 |
| 사용자 승인 | NOT REQUIRED | `approval_id=NULL`, 기술 QA만 수행 |
| 레거시 승인형 n8n | INACTIVE | `AtemoyaRevenueAutopilot01 active=false`; 진행 가능 24건은 rejected, 미결 승인 5건은 deferred, pending 0 |
| 대시보드 | LIVE | direct 10건의 예약·상태·공개 URL과 다음 시각을 `/api/status`에서 반환 |
| 로컬/클라우드 토큰 | ZERO FOR PUBLISH | 원고와 링크가 확정된 JSON manifest를 결정론적으로 렌더링. Ollama/Gemini 호출 없음 |
| 수익 | OBSERVED ZERO | 쿠팡 포털에서 확인한 현재 수익·판매는 0. 게시량 증가를 매출 증가로 표현하지 않음 |
| 유입 측정 | UNKNOWN | GA4/Coupang 실수신 행이 대시보드에 아직 없음. UNKNOWN을 0 조회로 바꾸지 않음 |

## 다음 실행 큐

1. 네이버 앱에서 현재 Chrome의 QR을 스캔하면 첫 LED 글을 편집기에 입력하고 공개 직전 내용·링크를 다시 검사한다.
2. 2026-09-15 09:00 KST: `요가매트 두께와 방 크기 맞추는 기준` 직접 게시 대상. 15분 poll SLA에 따라 09:15까지 실행·검증한다.
3. 이후 [18번 운영 설계](18-autonomous-volume-publication.md)의 표에 따라 하루 최대 3건, 총 10건에서 자동 중단한다.
4. 실패가 발생하면 같은 아티팩트만 재시도한다. 콘텐츠·링크·해시 오류는 후속 전부를 멈추고 대시보드와 Watchdog에 표시한다.
5. 이번 10건 완료 후에는 측정과 호스트 결정 없이 새 배치를 자동 생성하지 않는다.

## 이번 변경의 실제 결과

- `db/migrations/014_direct_affiliate_publication.sql`: 작업 payload, 상태·lease 제약, 인덱스와 직접 게시 상태 뷰.
- `ops/affiliate-publication/coupang-volume-pilot-20260914.json`: 검증된 기존 10개 쿠팡 링크를 사용하는 추가 10개 원고와 일정.
- `tools/affiliate_direct_publisher.py`: 링크·본문·권한·해시를 재검증하고 격리 worktree에서 `main`으로 게시 후 공개 HTTP를 확인.
- `tools/seed_affiliate_publication_batch.py`: public content/revision/offer/link/publication/job을 한 트랜잭션으로 멱등 저장.
- `com.atemoya.affiliate-direct-publisher`: 로그인 화면 없이 15분마다 실행.
- 대시보드와 Watchdog: 직접 게시 진행률, 다음 일정, 정체·중단 상태를 운영 표면에 추가.
- 기존 두 LED 페이지의 중복 `data-link-key`를 분리하고 전체 제휴 페이지에서 추적키 고유성을 검사.

## 실패와 사용자 개입 기준

사용자에게 다시 물어보지 않고 자동으로 처리하는 범위:

- 일시적인 Git/네트워크 오류 재시도
- 공개 URL 전파 지연 재확인
- 만료된 실행 lease 회수
- 사이트·고지·tracking·공개 경계 회귀 검사

사용자 결정이 필요한 경우:

- 사용자가 게시 루프 중단을 원할 때
- 10건 상한을 넘는 새 상품·새 플랫폼·유료 유입을 시작할 때
- 상업 운영 호스트·도메인을 확정할 때
- 포털이 2FA, 약관 동의, 결제 또는 본인 확인을 요구할 때

GitHub Pages의 남은 7건에는 사용자가 할 일이 없다. 네이버 첫 게시에는 저장된 로그인 정보가 없으므로, 열린 QR을 네이버 앱으로 스캔하는 동작만 필요하다. 비밀번호·OTP는 채팅이나 저장소에 남기지 않는다.

## 남은 P1/P2

1. P1: GitHub Pages는 상업 거래 중심 호스팅에 제한이 있다. 이번 10건을 제한된 편집 파일럿으로 끝내고 다음 배치 전에 상업 허용 호스트 ADR을 확정한다.
2. P1: 자연 조회·제휴 클릭·쿠팡 외부 판매를 수신한다. 수신 전에는 효과를 판단하지 않는다.
3. P1: 쿠팡 보고서의 중복 클릭 헤더, 주문/취소/수익 grain을 실제 데이터와 공식 정의로 확인한 뒤 importer를 연결한다.
4. P1: 다중 귀속·다중 비용·혼합 통화 회귀 테스트를 추가한다.
5. P2: 게시 10건 완료 후 카테고리별 조회·클릭을 비교해 다음 글을 선택한다. 수량만 자동 확대하지 않는다.

## 검증 기록

- DB 백업: `/Users/orange/Atemoya/backups/20260913T235613Z`, `/Users/orange/Atemoya/backups/20260913T235720Z`, `/Users/orange/Atemoya/backups/20260914T001323Z`.
- direct publisher 단위 테스트 9개 PASS.
- Watchdog 단위 테스트 11개 PASS.
- 첫 세 공개 URL: LED 마스크, 밀폐용기, 로봇청소기 페이지.
- 공개 commit: `356164df0074d557789c52fc881502095ed075cd`, `19562a5ce811d131aa1ad16491ccfd84a43c8b8d`, `c5e3898e17505b2558f5d66eafe6a48a1f7c4735`.
- 첫 Pages 실행 `34791301806` 및 tracking 무결성 보강 실행 `34791632103`: completed/success.
- 전역 affiliate 검사 기준 공개 commit: `6ae3d89f1e352d14912aa148b16143ca4df1c2ef`.
- DB: 첫 3개 job `succeeded`, publication `published`, 각 attempt 1·verified_at 기록. 나머지 7개는 queued.
- n8n DB: `AtemoyaRevenueAutopilot01 active=false` 확인.
- 레거시 격리 전 백업 `/Users/orange/Atemoya/backups/20260914T000846Z`; 삭제 없이 pending approval 0 확인.
- Dashboard API·DB 원장: 3건 published와 다음 2026-09-15 09:00 예약을 반환.

## 관련 기록

- [승인 없는 수량 확대 상세 설계·구축](18-autonomous-volume-publication.md)
- [왜 같은 질문을 반복하게 했는가](12-repeat-question-root-cause.md)
- [조회·클릭·수익 측정 경로](10-measurement-map.md)
- [10개 원래 카테고리 링크·게시 증거](16-ten-category-publication-plan.md)
- [운영 대시보드 점검](14-dashboard-audit.md)
- [네이버 블로그 첫 게시 설계·실행 기록](19-naver-blog-publication.md)

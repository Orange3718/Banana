# 07. 변경 기록과 개선 전후 비교

작성일: 2026-09-13 KST · 기준 원본: ATEMOYA_AFFILIATE_BUSINESS_OS.md SHA-256 3553c08027f7c3acd9c227137a6828a8a9a89579f3e52e15b237699cbb14fd87

이 문서는 설계 개선과 I01–I04 구축 변경을 한 곳에서 추적하는 기록이다. 실제 변경이 없는 운영 구성요소는 unchanged로 표시한다. 추측한 기능은 구현 완료로 적지 않는다.

## 전후 비교

| 영역 | 개선 전 | 개선 후 | 근거 / 효과 |
|---|---|---|---|
| 운영 상태 | 범용 단계와 기존 자동화가 함께 기술됨 | 01 문서에서 기존 객체·소비자·경계를 분리 | 기존 content, approval_requests, revenue_autopilot_jobs와 신규 흐름의 중복 실행 방지 |
| 제휴 공급자 | provider-agnostic adapter 목록만 존재 | 03에 capability와 실제 보고서 필드 증거 상태를 분리 | 승인·보고·추적키를 확인하기 전 adapter 완성을 주장하지 않음 |
| 데이터 모델 | content, click, conversion, revenue 필드 목록 | affiliate schema에서 revision, link, batch, fact version, journal, payout, cash를 분리 | 원본·현재값·정정·현금을 같은 행에 섞지 않음 |
| 귀속 | 상품·콘텐츠 연결이 암묵적 | content_exact / experiment_exact / program_only / unattributed 명시 | 연결 불가능한 금액을 임의 배분하지 않음 |
| 수입 | 보고서 수입과 revenue 기록이 한 단계 | raw → validate → normalize/quarantine → post, idempotency | 중복·겹친 기간·schema 오류가 원장에 바로 반영되지 않음 |
| 금액 | 예상 매출 공식 중심 | pending / confirmed / receivable / cash / contribution 분리 | 확정 전 수수료와 실제 입금을 이익으로 혼동하지 않음 |
| 정정 | 취소·지급공제·늦은 보고 계약 없음 | immutable fact version + delta journal + payout adjustment + 보상 행 | 원장 수정·삭제 없이 이력과 현재 잔액을 재현 |
| 승인 | QA 통과와 사람 승인 경계가 모호 | revision + policy + artifact hash binding | 승인 후 본문·링크 변경으로 승인 우회 방지 |
| 게시 | 기존 Publisher의 특정 feature branch/Pages 감지 | 신규 publication contract와 allowlist·manifest·revision 검증 | 설계와 기존 publisher의 운영 상태를 섞지 않음 |
| 클릭 측정 | 페이지 이벤트를 DB로 보낸다는 수준 | 공개 events/v1와 내부 pull/ack 분리 | collector 장애가 구매 이동을 막지 않으며 공개 입력을 원장에 직접 쓰지 않음 |
| KPI | CTR·EPC·매출 정의가 일반적 | 분모, maturity, currency, completeness, attribution level 필수 | 0과 미수집·지연·소표본을 구별 |
| 실험 | 여러 카테고리에 10–20개 자산 제안 | 고객·시장·언어·공급자 1개, 콘텐츠 3–5개 제안 | 유입·정산을 확인하기 전 양산하지 않음 |
| 호스팅 | GitHub Pages가 기본 운영 호스트로 서술 | GitHub는 source of truth, 운영 호스트는 ADR 미결 | 상업 이용 조건·이전 비용을 출시 전에 확인 |
| 운영 | retry·backup이 개념 수준 | lease, fence token, outbox, quarantine, 복구 테스트 계약 | 부분 성공과 재실행의 중복 효과를 제한 |

## 구현 변경 로그

| 변경 ID | 파일 | 변경 | 상태 | 검증 |
|---|---|---|---|---|
| C01 | db/migrations/013_affiliate_core.sql | affiliate schema, FK/UQ/CHECK, fact posting, outbox/checkpoint/time cost | 완료(I01–I04 범위) | migration 적용, `./ops/scripts/verify.sh` PASS |
| C02 | tools/verify_affiliate_core.py | 합성 수입·정정·중복·통화 차단·전달 제어 테스트 | 완료(I01–I04 범위) | F01–F07 PASS, transaction rollback |
| C03 | docs/affiliate-os/08-reflection.md | 구축 중 발견·인지하지 못한 부분 기록 | 진행 중 | 실제 provider 샘플 수령 시 갱신 |
| C04 | 기존 n8n·Publisher·Pages | 변경 없음 | 유지 | preflight, 코드·워크플로 읽기 검토 |

## 결정 기록

### D-013-1 — 신규 schema를 public과 분리

- 결정: affiliate schema를 사용하고 기존 public.revenue, public.content를 신규 수익 원장으로 직접 변경하지 않는다.
- 이유: 기존 제약·소비자·운영 이력이 있고, 두 흐름의 원장을 합치면 중복·회귀 위험이 커진다.
- 되돌림: schema와 기능 flag를 제거할 수 있지만, 이미 기록된 테스트·운영 원장을 삭제하지 않는다. 보상/격리로 처리한다.

### D-013-2 — 원장 함수는 결정론적 SQL, AI는 설명만

- 결정: delta, 중복, 상태, 통화, 귀속은 PostgreSQL 함수·제약으로 처리한다.
- 이유: 같은 입력에 같은 금액을 얻고 모델의 문장이나 confidence가 돈 계산을 바꾸지 않게 한다.
- 되돌림: 함수 버전과 journal 이력을 보존하고 새 버전으로 정정한다.

### D-013-3 — 공급자 실데이터 없이 fixture 구축

- 결정: 실제 계정·보고서 샘플이 없는 동안 provider=fixture만 사용한다.
- 이유: I01–I04의 코드·정산 구조는 외부 인증 없이 검증할 수 있고, 실제 기능이 미확인인 상태에서 계정·정책을 추측하지 않는다.
- 제한: fixture 통과는 Klook·Coupang·Amazon 연동 성공이 아니다.

### D-013-4 — 운영 migration은 백업과 verification 뒤

- 결정: 실행 전 백업 경로를 확보하고, migration 후 ops/scripts/verify.sh와 affiliate fixture 검증을 모두 통과시킨다.
- 이유: 현재 DB가 운영 기억이며 기존 workflow와 공유한다.
- 제한: 이 변경은 schema additive이지만 운영 복원 훈련을 대체하지 않는다.

실행 증거: 2026-09-13 UTC `./ops/scripts/backup.sh` → `/Users/orange/Atemoya/backups/20260913T092453Z`; 이후 migration 적용, `./ops/scripts/verify.sh` 및 `python3 tools/verify_affiliate_core.py` PASS.

## 이번 단계의 비변경

- 외부 제휴 계정 로그인·가입·2FA·약관 동의 없음.
- 실제 클릭 생성·자가 구매·광고비·유료 API 호출 없음.
- 기존 Telegram webhook, n8n workflow, Pages 호스팅, public.revenue 변경 없음.
- 공개 콘텐츠·사이트·배포 브랜치 변경 없음.

### D-013-5 — 첫 공급자는 쿠팡파트너스

- 결정: 첫 provider를 Coupang Partners로 고정한다.
- 이유: 사용자가 선택했고, 공식 사이트에서 광고 생성·성과 리포트·정산 흐름의 존재를 확인했다.
- 제한: 공개 사이트 설명만으로 계정 승인, API, report columns, 수수료율, 귀속키를 확정하지 않는다.
- 다음 증거: 익명화 성과 보고서 2개, 계정·도메인 승인, 링크 규칙, 정산·취소 상태.
- 기존 저장소 기록에 쿠팡 로그인 세션과 `link.coupang.com` 추적 링크가 있어 신규 계정 연결은 요청하지 않는다. 필요한 것은 현재 세션/권한 재검증과 보고서 증거다.

### D-013-6 — 승인 게이트 제거

- 결정: 사용자의 명시적 상시 지시를 affiliate 직접 게시 권한으로 기록하고 별도 Telegram/Owner 승인 요청을 만들지 않는다.
- 유지 통제: QA, 최종 artifact hash, 공개 파일 allowlist, 제휴 고지·링크, idempotency, rollback 기록.
- 기존 경로: `public.approvals`와 레거시 Publisher는 호환 모드로 보존하며 신규 affiliate publication과 섞지 않는다.
- 놓쳤던 이유: 기존 설계의 승인 안전장치를 사용자 운영 지시보다 상위 기본값으로 남겨 새 경로에도 잘못 적용했다. 반복 원인은 문서 권한 모델과 실행 스키마를 같은 변경에서 재검증하지 않은 것이다.
- 2026-09-13 현재 포털에서 로그인·`리포트`·`링크 생성`·`파트너스 API` 메뉴를 확인했다. API 키 생성 버튼은 비활성화되어 있어 API 연동을 완료로 간주하지 않는다.
- 같은 날 수익 요약에서 8월·9월 수익과 구매/취소 금액이 모두 ₩0임을 확인했다. 8월 최종 정산은 9월 25일 확정 예정으로 표시되어, 현재는 수익 부재와 정산 미확정을 분리해 기록한다.
- 기존 LED 마스크 2개 페이지에 새 상품 링크를 연결해 `main`에 직접 게시했다. GitHub Pages HTTP 200, 링크·쿠팡 고지 문구를 확인했다.

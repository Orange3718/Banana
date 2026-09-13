# 08. 구축 반추 기록

이 문서는 설계를 구현하면서 드러난 가정, 놓친 부분, 다음 검토 질문을 기록한다. 사실과 해석을 구분하고, 같은 문제가 반복되면 상세 설계와 체크리스트를 갱신한다.

## 2026-09-13 — I01–I04 시작

### 확인한 내용

- 기존 PostgreSQL은 public.content, public.revenue, public.cost, public.experiments, public.approvals, public.approval_requests, public.revenue_autopilot_jobs를 함께 사용한다.
- 기존 public.revenue는 amount가 음수가 될 수 없고, 기존 Publisher는 approval_requests와 특정 feature branch를 사용한다.
- 원본 설계의 새 테이블 목록만 추가하면 기존 소비자·상태·외래키와 충돌할 수 있다.
- 실제 affiliate 보고서 파일을 찾지 못했으므로, 공급자별 grain·정정·tracking key는 여전히 UNKNOWN이다.

### 내가 놓치기 쉬운 부분

- 일별 aggregate 보고서를 개별 주문처럼 분해하면 가짜 전환 수가 생긴다.
- IF NOT EXISTS migration은 존재하는 테이블에 새 제약·컬럼을 보장하지 않는다.
- 승인 테이블이 두 개면 숫자 ID나 상태가 우연히 같아도 같은 승인이라고 볼 수 없다.
- 페이지 클릭 수집이 되더라도 공급자 보고가 없으면 수익이 생긴 것이 아니다.
- 데이터가 0이라는 값과 데이터가 수집되지 않았다는 상태는 분석적으로 다르다.
- 정적 사이트 파일을 저장소 루트 전체로 배포하면 운영 문서나 내부 산출물이 공개될 수 있다.

### 설계에 반영한 개선

- raw/reference, normalized fact, immutable journal, payout, cash movement를 분리한다.
- 동일 원본·동일 version 재수입은 0 delta, 같은 version의 다른 내용은 conflict다.
- 공개 이벤트는 관측 데이터로만 취급하고 수익 원장 writer 권한을 주지 않는다.
- 승인 대상은 최종 artifact hash이며, revision·policy·target과 함께 묶는다.
- AI는 근거 정리와 설명을 맡고 금액·권한·상태 전이는 결정론적 코드가 맡는다.
- `013_affiliate_core.sql`을 적용하며 위 경계를 실제 FK/UQ/CHECK와 `post_fact_version` 함수로 고정했다. 합성 fixture는 재수입·정정·현금 뷰까지 통과했지만 실제 공급자 포맷의 증거는 아니다.
- 2차 점검에서 설계의 outbox·pull checkpoint·time entry·legacy cost 연결이 초기 DDL에서 빠진 것을 발견해 보강했다. 구현 범위가 커질수록 문서의 엔터티 목록과 실제 DDL을 자동 대조하는 검사가 필요하다.

### 아직 답하지 못한 질문

- 첫 공급자의 현재 보고서에 실제로 어떤 stable key와 sub-ID가 있는가?
- 정산 수수료 공제·원천세·환율을 내부 관리 손익과 회계 처리에서 어떻게 분류할 것인가?
- 운영 상업 호스팅과 도메인 이전을 언제 결정할 것인가?
- 자체 이벤트 수집이 개인정보·동의·브라우저 차단 정책에 어떻게 맞는가?
- 기존 공개 콘텐츠를 새 revision 소유권으로 옮길 필요가 있는가?

### 다음 반추 트리거

- 실제 보고서 첫 샘플을 받는 즉시 이 문서를 갱신한다.
- 첫 합성 fixture가 실패하면 원인을 schema/함수/테스트 가정으로 분리한다.
- migration을 운영 DB에 적용하기 전 백업·복원 결과를 기록한다.
- 첫 실제 자연 전환 뒤 귀속 수준과 현금 대사를 다시 검토한다.
- 복원 훈련을 완료하기 전까지 백업 성공을 복구 가능성으로 해석하지 않는다.
- `F01–F07 PASS`는 구조·멱등성·통화 경계를 증명할 뿐, provider report mapping·실제 공개 수집·승인 게시 성공을 증명하지 않는다.
- 사용자가 “승인 게이트 없음·직접 게시”를 명시했는데도 이전 문서의 Owner 승인 문구가 남아 있었다. 이는 권한 모델의 stale default이며, 이번에 direct_user_instruction 모드로 분리했다.

## 반추 작성 규칙

- Observed, Inferred, Unknown, Decision 태그를 사용한다.
- 사람의 실수로 표현하지 말고 어떤 통제·근거·경계가 부족했는지 쓴다.
- 원인을 확인하기 전 특정 공급자나 모델을 탓하지 않는다.
- 새 위험은 07-change-log-before-after.md의 이슈·완료 조건과 연결한다.

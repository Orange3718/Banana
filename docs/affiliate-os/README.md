# Affiliate Business OS 상세 설계 v1.2

**현재 실행 입구: [11. 실행 상태·다음 큐](11-execution-status.md). 반복 원인과 반영 내용: [12. 원인 분석·개선 전후](12-repeat-question-root-cause.md).**
실제 쿠팡 원본 확보 및 파일 검사 결과는 [13. 원본 검사](13-coupang-report-inspection.md)를 본다. 실제 헤더 샘플은 확보했지만 데이터 행·확정 정산 mapping은 아직 미검증이다.
상태 정정: DB core는 일부 구현됐지만 I01–I04 전체 인수 완료는 아니다. 과거 F01–F07 로그는 현재 CORE01–CORE07 smoke 검사이며 설계 fixture 전체와 동일하지 않다. 아래 구현 표현은 이 범위로 해석한다.

작성일: 2026-09-13 KST · 작성: OpenAI Codex / GPT-6 · 상태: CORE IMPLEMENTED · DIRECT PUBLISH MODE

이 문서 묶음은 기존 설계 리뷰의 B01–B04를 구체화하고, 구현된 affiliate core와 이후 게시·측정 계약을 연결한다. 핵심 DB schema와 멱등 원장은 운영 DB에 additive 적용됐고, provider parser·collector·게시 host는 후속 구현 대상이다.

## 읽는 순서

| 문서 | 구현자가 얻는 결정 |
|---|---|
| [01. 현행 상태와 경계](01-current-state-and-boundaries.md) | 기존 DB·승인·게시 경로, 재사용과 격리, 변경 영향 |
| [02. MVP와 결정 기록](02-mvp-and-decisions.md) | 첫 실험 가설, ADR, 예산·시장·호스팅 미결 사항 |
| [03. 공급자 계약](03-provider-contract.md) | 실제 확인 범위, adapter 계약, 필요한 보고서 필드와 중단 조건 |
| [04. 데이터와 정산](04-data-and-reconciliation.md) | 테이블·키·제약·귀속·정산 알고리즘·금액 검증 예시 |
| [05. 게시와 측정](05-publishing-and-measurement.md) | API·승인·배포·수집 상태·공개 경계·권한 |
| [06. 인수 기준과 운영](06-acceptance-and-runbook.md) | 구현 순서·실패 테스트·복구·출시 게이트 |
| [18. 승인 없는 수량 확대](18-autonomous-volume-publication.md) | 직접 게시 10건의 일정·기술 승인·배포·중단·운영 증거 |

## 범위와 준비도

- B01: 조회한 핵심 스키마와 저장소 코드의 재사용 매핑 완료. 전체 운영망·모든 소비자 감사를 완료한 것은 아니다.
- B02: 쿠팡 LED 마스크 파일럿과 직접 게시 운영방식 결정. 도메인·지출은 기존 제한을 유지한다.
- B03: 쿠팡파트너스를 첫 공급자로 결정하고 공통 입출력 계약을 고정했다. 실제 계정 보고서의 컬럼 매핑은 미확인.
- B04: provider-neutral 데이터·원장·수입 명세 완료. 실제 형식 샘플을 이용한 구현 검증은 다음 단계.
- G0: 직접 게시 권한 결정 완료. G1: core 합성 검증 PASS, 실제 provider parser 미완료. G2/G3: 미통과.

바로 구현 가능한 범위는 합성 데이터 기반 수입·정규화·원장·중복 방지·귀속·상태 전환의 격리 테스트다. 공급자별 실데이터 parser와 공개 배포는 해당 계약의 미결 항목을 해결해야 한다.

## 설계의 핵심 결정

1. 기존 `public` 테이블을 덮어쓰지 않고 신규 상업 데이터는 `affiliate` schema에 둔다.
2. 기존 게시기는 `approval_requests`를 쓰지만, 신규 affiliate publication은 `direct_user_instruction` 모드로 별도 운영한다.
3. 신규 Affiliate OS의 수익 원본은 신규 수수료 원장이다. 기존 `public.revenue`에 복제 합산하지 않는다.
4. 보고서가 제공하는 실제 단위까지만 귀속한다. 콘텐츠 미귀속 수익을 감추거나 임의 배분하지 않는다.
5. 방문자 구매 이동은 직접 제휴 링크, 측정은 비동기다. 공개 사이트는 iMac 장애와 분리한다.
6. 배포는 검토한 revision·링크·정책·아티팩트 해시와 결합한다. 최종 산출물 검증 뒤 링크를 바꾸지 않는다.

## 근거

- [원본 설계안](/Users/orange/Documents/Atemoya/ATEMOYA_AFFILIATE_BUSINESS_OS.md), SHA-256 `3553c08027f7c3acd9c227137a6828a8a9a89579f3e52e15b237699cbb14fd87`
- [선행 리뷰](/Users/orange/Documents/Atemoya/ATEMOYA_AFFILIATE_BUSINESS_OS_DESIGN_REVIEW_AND_BUILD_PLAN.md), SHA-256 `0c4db1cac0500ea133289638990a20a61ad695421dfadc454b627925fe868f14`
- 조사 저장소: `Orange3718/Banana`, 기준 commit `916b182c2a45e3efbb6addf62498805856970f79`.
- 현재 작업 브랜치: `feat/atemoya-publication-record`. 구현 기준 브랜치는 작업 시작 시 원격과 재대조한다.
- 검토 원칙: [AI Review Charter](../../ai-framework/reviewer/review_charter.md).

`OBSERVED`는 이번 직접 확인, `DOCUMENTED`는 문서 근거, `DESIGN`은 이번 설계 결정, `PROPOSED`는 제안, `UNKNOWN`은 미확인이다. 공급자 기능 확인과 계정 사용 승인은 별개의 상태다.

## 문서 검증 기록

2026-09-13: affiliate 문서 내부 링크·코드 블록·원본 보존을 검사했고, migration 적용·F01–F07·운영 verify를 실행했다. 직접 게시 권한은 사용자 상시 지시로 기록했고, API 키·provider report·collector·host는 미완료로 남겼다.

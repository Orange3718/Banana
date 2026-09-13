# Affiliate Business OS 상세 설계 v1.0

작성일: 2026-09-13 KST · 작성: OpenAI Codex / GPT-6 · 상태: DESIGN READY WITH OPEN CONTRACTS

이 문서 묶음은 기존 설계 리뷰의 B01–B04를 구체화하고, 이후 구현에 필요한 게시·측정·검증 계약까지 연결한다. 모든 신규 테이블·API·예약·호스팅은 목표 설계이며 이번에 설치하거나 활성화하지 않았다.

## 읽는 순서

| 문서 | 구현자가 얻는 결정 |
|---|---|
| [01. 현행 상태와 경계](01-current-state-and-boundaries.md) | 기존 DB·승인·게시 경로, 재사용과 격리, 변경 영향 |
| [02. MVP와 결정 기록](02-mvp-and-decisions.md) | 첫 실험 가설, ADR, 예산·시장·호스팅 미결 사항 |
| [03. 공급자 계약](03-provider-contract.md) | 실제 확인 범위, adapter 계약, 필요한 보고서 필드와 중단 조건 |
| [04. 데이터와 정산](04-data-and-reconciliation.md) | 테이블·키·제약·귀속·정산 알고리즘·금액 검증 예시 |
| [05. 게시와 측정](05-publishing-and-measurement.md) | API·승인·배포·수집 상태·공개 경계·권한 |
| [06. 인수 기준과 운영](06-acceptance-and-runbook.md) | 구현 순서·실패 테스트·복구·출시 게이트 |

## 범위와 준비도

- B01: 조회한 핵심 스키마와 저장소 코드의 재사용 매핑 완료. 전체 운영망·모든 소비자 감사를 완료한 것은 아니다.
- B02: 기술 설계 기본값과 파일럿 제안 완료. 시장·제휴 계약·도메인·지출의 Owner 결정은 미확정.
- B03: 공급자 후보 조사와 공통 입출력 계약 완료. 실제 계정 보고서의 컬럼 매핑은 미확인.
- B04: provider-neutral 데이터·원장·수입 명세 완료. 실제 형식 샘플을 이용한 구현 검증은 다음 단계.
- G0: 일부 미결. G1/G2/G3: 아직 미통과. 문서 완성과 운영 출시 준비를 구분한다.

바로 구현 가능한 범위는 합성 데이터 기반 수입·정규화·원장·중복 방지·귀속·상태 전환의 격리 테스트다. 공급자별 실데이터 parser와 공개 배포는 해당 계약의 미결 항목을 해결해야 한다.

## 설계의 핵심 결정

1. 기존 `public` 테이블을 덮어쓰지 않고 신규 상업 데이터는 `affiliate` schema에 둔다.
2. 현재 게시기는 `approval_requests`를 쓴다. 새 승인에는 `public.approvals`와 신규 binding을 사용하고 기존 게시 큐와 섞지 않는다.
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

2026-09-13: 7개 파일의 내부 링크·코드 블록·원본 보존을 검사했고, 12개 선행 리뷰 이슈의 연결을 확인했다. 정산 예제의 핵심 산술 7건을 검산했다. 구현 인수 테스트 22건과 fixture F01–F12는 설계 명세이며 실제 애플리케이션 테스트를 실행한 결과가 아니다. 현재 문서는 로컬 저장 상태이며 Git 커밋·푸시·공개 배포는 수행하지 않았다.

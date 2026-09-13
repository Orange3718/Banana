# 06. 인수 기준·구축 순서·운영 런북

v1.1 · IMPLEMENTED CORE · I01–I04 보강 구현 및 합성 검증 완료; I05–I09는 실제 provider/호스팅 증거 대기

## 1. 구현 작업 분해

| 순서 | 작업 | 구체 산출물 | 통과 조건 |
|---|---|---|---|
| I01 | 격리 테스트 DB와 schema | migration, FK·CHECK·UQ, public fixture | 적용 및 기존 런타임 검증 PASS |
| I02 | 파일 import 및 contract 검사 | manifest·canonical validator, quarantine | 정상/오류/요약행 구분, 합성 fixture 재현 |
| I03 | fact version·journal posting | transaction·잠금·누계 delta·중복 방지 | F01–F07 PASS |
| I04 | 귀속·payout·cash·cost 조회 | 명시적 근거·기간·통화·품질 상태 | 총액 불변·순현금 4500 사례·미귀속 보존 |
| I05 | 실제 공급자 parser | 익명화 실제 샘플, field mapping, policy version | G1의 실제 형식 검증 완료 |
| I06 | revision·approval·publication | binding, Owner adapter, 배포 mock | 오래된 승인·다른 artifact·부분 성공 테스트 |
| I07 | collector·pull API | mock durable store, export/ack, dedup | 장애·재전송·gap·클릭 이동 독립 검증 |
| I08 | 운영 host 연결·최종 QA | dist-public, manifest, 배포/롤백 기록 | G2 통과 후 허용된 파일럿만 게시 |
| I09 | 데이터 성숙·실험 판정 | decision_rules v1, data readiness, 보고 | 소표본·미수집의 잘못된 확대/중단 0건 |

I01–I04의 핵심 구현과 합성 검증은 완료했다. I05는 실제 보고서가 필요하고, I06–I09는 승인 어댑터·공개 수집기·호스팅·자연 전환 증거가 필요하다.

## 2. 테스트 추적표

| ID | 시나리오 | 기대 결과 | 근거 |
|---|---|---|---|
| T01 | 글 A/B 동일 상품, 추적키 없음 | program_only, 글별 수익 null | R01 / F05 |
| T02 | 다른 상품 구매, A 공식 tracking key | A 귀속, 구매 상품 보존 | R01 / F06 |
| T03 | 동일·중첩 파일·parser 재처리 | 금액·건수 추가 0 또는 변화 delta만 | R06 / F02/F07/F11 |
| T04 | 늦은 취소·공제·입금 | 예상/확정/현금 분리, -receivable 허용 | R02 / F01/F03/F04/F10 |
| T05 | 누락열·다른 통화·잘못된 상태 | batch 격리, 원장 무변경 | R07 |
| T06 | 승인 후 hash 변경·만료·다른 사용자 | dispatch 거절·감사 기록 | R05 |
| T07 | 배포 성공 뒤 DB 기록 실패 | 동일 deployment 복구, 새 게시 없음 | R06 |
| T08 | iMac/collector 중단·JS 비활성 | 페이지·직접 제휴 이동 유지 | R04 |
| T09 | 이벤트 중복·위조·oversize·rate 초과 | 제한, 원장 영향 없음 | R04 |
| T10 | 근거에 악성 명령·허위 후기·오래된 가격 | 권한 불변·QA 차단 | R10 |
| T11 | 0분모·미수집·소표본·미성숙 기간 | N/A/WAIT_FOR_DATA, 자동 확대 없음 | R08 |
| T12 | schema 적용·구버전 조회·복원 | 기존 계약 보존, 복원 후 대사 | R11 |
| T13 | 동일 series 동시 posting 2개 | UQ·잠금으로 단일 효과 | R06 |
| T14 | summary와 detail 동시 보고 | detail 총액만 전기 | R02 / F09 |
| T15 | 같은 version 다른 내용·구버전 도착 | conflict/stale, 현재 잔액 보존 | R06 / F08 |
| T16 | 귀속 mapping 나중 보완 | 전체 금액 불변, 귀속 이력 유지 | R01 / F12 |
| T17 | PG commit 뒤 ack 실패 | 다시 읽고 dedup, 손실 없음 | R04 |
| T18 | export 도중 늦은 event 도착 | 다음 batch 포함, cursor로 누락하지 않음 | R04 |
| T19 | artifact 검사 후 링크 변경 | hash 불일치로 게시 거절 | R05 |
| T20 | dist에 docs/SQL/private 파일 존재 | release 검사 실패 | R03/R04 |
| T21 | 기존 승인 숫자와 신규 승인 숫자 충돌 | namespace·FK로 잘못된 승인 연결 거절 | R05/R11 |
| T22 | budget null·cap 초과 | 유료 dispatch 거절, 사유·잔여량 표시 | R12 |

## 3. 판정 규칙의 테스트 가능한 입력

decision input은 immutable metric snapshot이다. 필드: experiment_id, time_window, currency, data_as_of, report_complete, mature, observed_sample, required_sample, attribution_level, confirmed_commission, recognized_direct_cost, owner_minutes, policy_state, rule_version.

평가 순서:

1. policy_state가 금지/정지이면 PAUSE_REVIEW.
2. 데이터 누락·지연·불완전·미성숙·필수 표본 미설정·표본 부족이면 WAIT_FOR_DATA.
3. 최소 귀속 수준 미달이면 WAIT_FOR_ATTRIBUTION.
4. 충분한 근거에서 비용·시간 상한 초과면 UPDATE 또는 STOP_PROPOSED.
5. 반복 전환·양의 공헌이익·범위 내 운영이면 EXPAND_PROPOSED.
6. 명확한 개선 가설이면 UPDATE, 그 외 KEEP.

계속/중단의 논거를 JSON으로 저장하고 AI는 그것을 설명한다. AI 문구가 rule 결과를 바꾸지 않는다. EXPAND_PROPOSED/STOP_PROPOSED는 실행 권한이 아니라 검토 결과다.

## 4. 운영 지표와 경보

| 신호 | 기본 제안 임계값 | 대응 |
|---|---|---|
| pull 지연 | 15분 초과 | 중복 억제 경보, collector backlog 확인 |
| 공급자 보고 지연 | contract 예정시각 +24시간 | delayed, 수익 0으로 대체하지 않음 |
| batch control total 차이 | 0 초과, 설명 없는 차이 | 전기 중단·격리 |
| lease 만료 | job별 만료, publisher 10분 | 외부 결과 조회 후 회수, fence token 증가 |
| 미ack 이벤트 만료 임박 | 만료 24시간 전 | backlog 복구 우선, gap 위험 알림 |
| 예산 | 80% 경보, 100% 신규 유료 job 거절 | 잔여 예약 예산 포함, 무료라 추정하지 않음 |
| 승인 대기 | 24시간 초과 | 한 번 묶어 알림, 만료 시 재요청 상태 |
| 외부 사이트 상태 | 별도 장애 영역에서 15분 이내 탐지 목표 | 공개 경로·배포 revision 대조 |

비용 통제는 job 시작 전 예상 비용 예약 → 결과 후 정산으로 한다. 알림만 설정했다고 실제 공급자 과금이 자동 중단된다고 보장하지 않는다. 플랫폼 지출 한도·API 한도·큐 dispatch 제한을 함께 확인한다.

## 5. 장애 런북

### A. 보고서 합계 불일치

batch를 quarantine하고 이후 확정 수익 계산에서 제외한다. 원본 해시, contract version, 통화별 합계, 중복/요약행 포함 여부를 확인한다. 정상 원장은 보존한다. 수정 parser는 과거 fixture 회귀 통과 후 같은 원본을 새 contract version으로 재처리한다. 원장 직접 숫자 수정은 금지한다.

### B. 배포 후 상태 불일치

publication의 target·artifact hash·외부 deployment reference를 확인한다. 공개 URL이 다른 revision이면 published로 기록하지 않는다. 같은 결과가 이미 공개된 경우 상태만 복구한다. external side effect를 찾을 수 없으면 manual_review로 두고 무조건 재시도하지 않는다.

### C. iMac 중단

외부 사이트·직접 제휴 링크는 계속 동작한다. collector는 내구성 버퍼에 보관한다. 복구 후 DB health → schema version → 미완료 posting transaction 상태 → pull 재개 → batch ack 순으로 확인한다. 손실 구간이 있다면 해당 기간 지표를 partial로 표시한다.

### D. 승인 또는 계정 권한 변경

해당 신규 작업의 dispatch를 중지한다. 기존 게시물을 무조건 삭제하지 않고 공개 위험을 평가한다. 만료·철회된 정책은 새 배포에 사용하지 않는다. 토큰 회전은 secret store에서 수행하고 문서·Git에 기록하지 않는다.

### E. 백업 복원

RPO 24시간·RTO 4시간은 초기 목표다. 외부 위치의 DB 백업·private 보고서·정책/템플릿·호스팅 manifest·credential 복구 참조를 확보한다. 격리 환경에서 복원 후 journal 합계, current version pointer, FK, 원본 hash, publication ownership을 검사한다. collector에서 재수입 가능한 이벤트와 공급자 원본 보고로 공백을 회복한다. 실제 복원 훈련 전 목표 충족으로 보고하지 않는다.

## 6. 출시 게이트와 남은 증거

| 게이트 | 현재 | 종료 증거 |
|---|---|---|
| G0 설계 기준 | 일부 미결 | D01/D02/D03/D04/D06/D07 결정, 실제 legacy 소비자 범위 확인 |
| G1 정산 | 부분 완료 | 현재 F01–F07 및 schema 회귀 PASS; 실제 형식 mapping과 T01–T05/T13–T16 필요 |
| G2 공개 파일럿 | 미실행 | 호스팅·도메인·계정 조건, T06–T10/T12/T17–T22, 복구·알림 검증 |
| G3 확대 | 데이터 없음 | 성숙 자연 전환·수수료·비용·Owner 시간, 규칙 기반 판단 |

설계 문서의 논리 검토와 링크 검사를 완료해도 위 테스트가 실행된 것으로 바뀌지 않는다. G1 이전에는 provider=fixture로 격리 구축할 수 있다. 운영 환경의 적용·공개 게시·지출은 이후 사용자 요청과 기존 권한 범위에 맞춘다.

## 7. 다음 작업 전달

상세 설계 이후 첫 구현 대상은 I01–I04다. 신규 feature worktree에서 진행하고 기존 운영 체크아웃의 Upbit 변경을 포함하지 않는다. 원격 기준 브랜치·AGENTS 지침을 다시 확인한다.

다음 작업의 종료 조건은 schema·수입·원장·조회 모듈이 합성 데이터에서 F01–F12를 통과하고 실제 공급자 미확인 항목을 명시하는 것이다. 실제 계정 샘플이 없더라도 구현 가능한 부분은 완료하되 계정 연동 성공으로 보고하지 않는다.

설계 변경이 필요하면 ADR 번호, 이유, 영향받는 테스트, 원장 호환성을 갱신한다. 기존 원본과 리뷰 문서는 보존하고 이 상세 설계 묶음에서 버전을 올린다.

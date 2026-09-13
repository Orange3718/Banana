# 03. 공급자·보고서 adapter 계약

v1.1 · R01/R02/R06/R07 · 실제 헤더 샘플 확보, 비어 있지 않은 데이터 의미 검증·정산 parser 미완료

2026-09-13 후속: 쿠팡 9/12 일별 XLSX를 기존 세션에서 확보했다. clicks/orders 헤더만 있고 데이터 행은 없으며, clicks 헤더가 중복된다. 원본 보존·검사기와 결과는 [13. 원본 검사](13-coupang-report-inspection.md)를 따른다. 아래 설계 계약을 실제 구현 완료로 읽지 않는다.

## 1. 조사 결과

| 후보 | 확인한 사실 | 아직 모르는 것 | 설계 역할 |
|---|---|---|---|
| Klook | 공식 안내에 Ticket List의 주문 내 activity 구분, 월별 보고·다운로드 설명 | 현재 계정 승인, 파일 형식/헤더, 안정 ID, sub-ID, 통화·정산 상태, API 자격 | 첫 여행 실험 후보 |
| Coupang Partners | 첫 공급자로 결정. 공식 사이트가 성과 리포트·정산 시스템·광고 생성 흐름을 설명 | 현재 계정 승인·도메인·실적 export 실제 컬럼·추적키·정산 상태 | 첫 MVP 공급자 |
| Amazon | 앞선 공식 Order Report 문서에 상품·다른 상품 주문·기간 차이 설명 | 사용자 계정·tracking ID 세부·현재 export | 공통 모델의 귀속 한계 참고 |

원본·리뷰 디렉터리 및 저장소 `inputs`, `channel-drafts`의 CSV/TSV/XLSX·보고서 이름을 좁혀 검색했으나 실제 제휴 정산 샘플을 찾지 못했다. 이는 사용자 전체 저장공간에 자료가 없다는 뜻은 아니다. 계정 로그인·민감 자료 검색 범위를 임의 확대하지 않았다.

Klook의 [공식 보고 안내](https://www.klook.com/en-US/blog/partner/tracking-your-performance/)는 2021-12-03 갱신, 이번 확인 2026-09-13이다. 공개 설명에 보고·다운로드가 있다는 사실과 실제 계정에 어떤 열이 있다는 판단을 구분한다. 특정 프로모션의 수수료 조건 등 과거 문구를 현재 정책으로 하드코딩하지 않는다.

[Coupang Partners](https://partners.coupang.com/) 공개 응답만으로 reporting API 계약을 확인할 수 없었다. 일반 판매자 Open API와 Partners API를 혼동하지 않는다. 가상의 endpoint·필드·수수료율을 공급자 계약으로 만들지 않는다.

## 2. Capability record

각 값은 supported/unsupported/unknown, 근거 reference, 검토일, 적용 계정·시장, 정책 버전을 가진다.

| capability | Klook 후보 현재값 | 운영 시 필요 증거 |
|---|---|---|
| account_approved | unknown | 계정의 현재 승인 상태 |
| domain_approved | unknown | 게시 도메인 등록·승인 |
| market_eligible | unknown | 첫 고객 국가의 결제·상품 이용·사업자 지급 가능성 |
| official_link_generation | documented, 계정 검증 대기 | 실제 발행 방식과 허용 형식 |
| report_download | documented, 계정 검증 대기 | 현재 익명화 파일 샘플 |
| reporting_api | unknown | 공식 API 문서·계정 권한 |
| report_tracking_key | unknown | 실제 헤더·값·정책상 의미 |
| stable_order_item_key | unknown | 서로 다른 보고 시점에서 같은 거래의 ID 유지 |
| payout_report | unknown | 실제 정산·지급 파일과 상태 정의 |
| redirect_allowed | unknown | 공식 정책; 기본 직접 링크 사용 |

`documented`는 capability의 사용 허용 상태가 아니라 증거 등급이다. 구현 record의 state는 unknown으로 두고 evidence_level=documented로 기록한다. unknown 기능은 호출·추정하지 않는다.

## 3. Adapter 인터페이스

도메인 모듈 입력은 파일 바이트 + manifest다. 원격 URL 다운로드를 parser에 맡기지 않는다. 수집·계정 인증은 별도 책임이다.

```text
inspect(bytes, manifest) -> format, encoding, headers, proposed_grain, issues
validate_contract(inspected, approved_contract) -> accepted | quarantined
normalize(bytes, contract_version) -> canonical rows + source row references
reconcile_control_totals(rows, manifest) -> totals, differences, quality
```

manifest 필수: account_id, environment, report_family, period_start/end, provider_timezone, currency 또는 행별 통화 여부, file_sha256, captured_at, source_ref, contract_version. 기간은 시작 포함·끝 제외다. 날짜만 있는 공급자 값은 공급자 timezone과 date precision을 보존하고 정확한 UTC 거래시각을 만들어내지 않는다.

report_family는 `activity_estimate`, `commission_confirmed`, `settlement`, `cash_receipt` 중 하나다. 상품 매출·예상 수수료·확정 수수료·실입금은 다른 의미다. 보고서 이름이 다르더라도 하나의 수수료를 두 authoritative stream에서 전기하지 않는다.

contract 필수: 원본 열→canonical 매핑, 단위와 상태 의미, 키 생성식, 보고 버전 순서, 전체/부분 snapshot 여부, 누락 행 의미, 통화 scale·반올림, 수정·취소 의미, control total, 기대 보고 주기, maturity rule.

## 4. Canonical row 계약

아래 이름은 Atemoya 내부 명세이며 공급자 CSV의 실제 헤더가 아니다.

| 필드 | 형식 | 규칙 |
|---|---|---|
| source_row_ref | string | batch ID + 원본 위치 |
| series_key | string | 같은 경제 대상을 보고 간 식별하는 안정 키 |
| grain | order_item / daily_aggregate | 실제 보고 단위. 임의 주문 분할 금지 |
| provider_version | string 또는 null | 비교 가능한 공급자 revision, 없으면 불명 표시 |
| observed_at | UTC timestamp | 자료 관찰 시각, 거래 시각과 별개 |
| activity_date | date | 공급자 기준 일자 |
| order_id / item_id | nullable string | 원본에 존재할 때만 |
| tracking_key | nullable string | 반환된 공식 ID, 개인정보 금지 |
| raw_status | string | 원본 상태 보존 |
| pending_balance | decimal string | 현재 미확정 수수료 잔액 |
| confirmed_cumulative | decimal string | 해당 경제 대상의 누적 확정 순수수료, 지급 후에도 감소하지 않음 |
| currency | 3-letter string | 원통화, 미확인 통화 추정 금지 |
| quantity | decimal string 또는 null | 주문수·상품수·티켓수 종류도 contract에 명시 |
| attribution_hint | structured | 공급자에서 얻은 후보 정보, 확정 귀속 아님 |

pending·confirmed를 함께 보고하지 않는 source는 제공하는 balance만 갱신한다. 제공하지 않은 값을 0으로 덮어쓰지 않는다. estimate→confirmed 전환 시 pending 해소를 증명하는 동일 대상 연결이 필요하며, 없으면 두 지표를 합산하지 않고 서로 다른 관측으로 표시한다.

## 5. 실제 샘플 입수 시 매핑 절차

1. 계정 식별자는 내부 surrogate로 교체하고 구매자 이름·주소·연락처를 제거한다. 금융 증빙 원본은 private 경로에 유지한다.
2. 서로 겹치는 기간의 보고서 2개와 수정/취소가 포함된 자료를 비교한다.
3. 원본 헤더·행 단위·고유키·수정 순서·정산과의 관계를 채운다.
4. 키 중복률·합계·수량·통화별 control total을 대조한다.
5. sub-ID가 없다면 program_only를 기본 귀속으로 한다. 한 프로그램에 한 실험만 있다는 이유로 실험 귀속을 확정하지 않는다.
6. 세부 행 합계와 전체 요약행은 같은 금액이다. summary 행은 대사용으로만 쓰고 전기 대상에서 제외한다.
7. 새 parser 버전은 합성·익명화 fixture 검증 후 승인한다. 파일 포맷 변화는 silent fallback하지 않는다.

실제 헤더 매핑 미결 목록: `series_key`, `provider_version`, `tracking_key`, `raw_status`, `currency`, `pending_balance`, `confirmed_cumulative`, 지급 ID·순입금·공제 항목. 이는 G1의 외부 자료 의존 조건이다.

## 6. 합성 fixture 정의

[04](04-data-and-reconciliation.md)의 F01–F09는 vendor-neutral 합성 예시다. Klook·Coupang 실제 파일 형식 또는 실제 매출이라고 표시하지 않는다. 구현 시 `environment=test`, `provider=fixture` 계정에서만 사용한다.

지원 수준별 fixture: 안정 주문항목 ID + 추적키, ID 없는 일별 완전 snapshot, 추적키 없는 보고서, 요약/세부 중복, 늦은 취소, 같은 버전 다른 값, 누락 필수열, 잘못된 통화, 구버전 보고서 지연 도착.

parser 버전과 fixture hash를 결과에 기록한다. 합성 테스트 통과는 내부 구현 가능성을 증명하며 실제 공급자 연동 통과를 대체하지 않는다.

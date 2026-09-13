# 04. 데이터·귀속·정산 상세 명세

v1.0 · DESIGN · R01/R02/R06/R08/R11 · 대상 PostgreSQL 16

## 1. 설계 범위와 표기

신규 schema는 `affiliate`. 아래는 구현할 물리 모델 명세이며 실행한 DDL이 아니다. `!`는 NOT NULL, `?`는 nullable, PK·FK·UQ는 기본키·외래키·고유제약이다. ID는 신규 UUID, 기존 public ID 참조는 bigint다. public 이름은 반드시 schema로 한정한다.

공통 형식: timestamp는 `timestamptz`, 공급자 일자는 `date`, 금액은 `numeric(20,6)`, 통화는 `varchar(3)` + 영문 대문자 CHECK, 해시는 64자리 hex CHECK. 금액 JSON은 문자열이다. 허용 통화별 scale을 contract에서 검증하고 계산 중 반올림하지 않는다. 지급·표시 시점의 반올림은 공급자 계약에 맞춘다.

운영 원시 파일은 접근 제한 파일/객체 저장소가 보관한다. DB의 source_ref는 허용 storage root 또는 검증된 object key이며 사용자 입력 임의 URL을 조회하는 기능이 아니다. 모든 신규 테이블의 삭제는 기본 RESTRICT, 업무 종료는 상태로 표시한다.

## 2. 엔터티 관계

```text
public.experiments 1 ─ 1 experiment_extensions
public.content     1 ─ 1 content_extensions ─ N content_revisions
content_revisions  1 ─ N link_versions ─ 1 offers ─ 1 program_accounts
content_revisions  1 ─ N approval_bindings ─ 1 public.approvals
content_revisions  1 ─ N publications
program_accounts   1 ─ N import_batches ─ N fact_versions ─ 1 fact_series
fact_versions      1 ─ N journal_entries
program_accounts   1 ─ N payouts ─ N cash_movements
public.experiments 1 ─ N cost_entries / time_entries
link_versions      1 ─ N click_events
```

FK로 경제 대상과 계정을 같이 검증한다. `id`가 유효해도 다른 계정의 링크·정산을 연결하면 거절한다. 필요한 경우 UQ(id,account_id)와 복합 FK를 사용한다.

## 3. 계약·실험·콘텐츠 객체

| 테이블 | 필수 컬럼·제약 | 변경 규칙 |
|---|---|---|
| program_accounts | id UUID PK; environment! test/prod; provider!; account_ref!; market!; state! inactive/ready/suspended; credential_ref?; UQ(environment,provider,account_ref) | credential 값 저장 금지. 비활성 상태로 생성 |
| policy_versions | id PK; account_id FK!; version int! >0; source_ref!; verified_at!; capabilities JSONB!; contract JSONB!; UQ(account_id,version) | append-only, 승인된 버전만 수입·게시 참조 |
| experiment_extensions | experiment_id bigint PK/FK public.experiments; primary_account_id FK!; market!; locale!; state_version int!; rules JSONB!; budget JSONB! | 규칙·예산 변경 시 버전 증가, 실행 중 변경 이력 기록 |
| content_extensions | content_id bigint PK/FK public.content; experiment_id FK!; primary_category!; locale!; target_market!; publisher_owner!; UQ(content_id,experiment_id) | 첫 구현은 신규 콘텐츠 전용. 기존 큐 소유권 검증 |
| content_revisions | id PK; content_id FK!; revision_no int!; body_text!; body_sha256!; evidence JSONB!; template_version!; created_at!; UQ(content_id,revision_no) | 본문·근거 immutable. 수정은 새 행 |
| offers | id PK; account_id FK!; external_item_id!; destination_url!; current_state!; checked_at?; UQ(account_id,external_item_id) | 상품 현재 상태. 과거 링크·가격 근거는 revision snapshot |
| link_versions | id PK; revision_id FK!; offer_id FK!; placement_key!; affiliate_url!; policy_version_id FK!; tracking_key?; evidence_ref!; UQ(revision_id,placement_key) | 링크 immutable, 실시간 URL 교체 금지 |
| tracking_bindings | id PK; account_id FK!; tracking_key!; content_id?; experiment_id?; valid_from!; valid_to?; evidence_ref! | 같은 계정·키의 유효기간 중첩 금지. content/experiment 중 명확한 한 범위 |

experiment rules JSON schema 필수값: version, success_metric, minimum_sample 또는 null, report_maturity_policy, decision_cadence, maximum_assets. budget 필수값: reporting_currency, monthly_cash_cap 또는 null, experiment_cash_cap 또는 null, owner_minutes_target 또는 null. null인 한도를 무제한으로 해석하지 않는다.

근거 evidence JSON 배열 항목은 claim_id, source_ref, observed_at, claim_text_hash, applicable_market, valid_until 또는 review_trigger, rights_reference를 가진다. 해당 사항 없는 필드는 null과 사유를 저장한다.

tracking key는 지연 전환을 고려해 실험 종료 뒤 다른 콘텐츠/실험에 재사용하지 않는 것을 v1 기본값으로 한다. 공급자 ID 한도로 재사용이 필요하면 최대 귀속·수정 기간과 보고 시각 의미를 확인한 후 별도 설계한다. 과거 데이터의 귀속은 당시 mapping으로 유지한다.

## 4. 보고·정산 객체

| 테이블 | 컬럼·제약 |
|---|---|
| import_batches | id PK; account_id FK!; policy_version_id FK!; report_family!; file_hash!; source_ref!; period_start/end!; captured_at!; provider_revision?; state!; data_quality!; UQ(account_id,report_family,file_hash,policy_version_id); CHECK period_start < period_end |
| fact_series | id PK; account_id FK!; family!; series_key!; grain!; currency!; current_version_id?; UQ(account_id,family,series_key) |
| fact_versions | id PK; series_id FK!; batch_id FK!; row_ref!; version_key!; content_hash!; raw_status!; event_date!; pending_balance?; confirmed_cumulative?; quantity?; tracking_key?; provider_item_id?; normalized_json!; UQ(series_id,version_key) |
| journal_entries | id PK; account_id FK!; series_id FK!; fact_version_id FK!; bucket! pending/confirmed; delta numeric(20,6)!; currency!; economic_date!; posted_at!; source_key! UQ; attribution JSONB! |
| payouts | id PK; account_id FK!; external_payout_id!; currency!; current_version int!; latest_components JSONB!; evidence_ref!; UQ(account_id,external_payout_id) |
| payout_adjustments | id PK; payout_id FK!; version int!; cleared_delta!; withheld_delta!; fee_delta!; net_expected_delta!; evidence_ref!; UQ(payout_id,version) |
| cash_movements | id PK; account_id FK!; payout_id FK?; external_statement_key!; paid_at!; currency!; signed_amount!; evidence_ref!; UQ(account_id,external_statement_key) |
| cost_entries | id PK; experiment_id FK?; content_id FK?; legacy_cost_id bigint FK public.cost?; economic_date!; paid_at?; currency!; recognized_amount!; cash_outflow?; classification!; evidence_ref!; source_key! UQ; reversal_of FK? |
| time_entries | id PK; experiment_id FK!; content_id FK?; occurred_at!; minutes integer! >=0; actor_role!; activity!; source_key! UQ |
| fx_rates | id PK; base_currency!; quote_currency!; rate numeric(24,12)! >0; rate_date!; source_ref!; UQ(base_currency,quote_currency,rate_date,source_ref) |

원본 행은 private 참조로 보존하고, 정규화에 필요 없는 구매자 개인정보는 DB·Git에 복사하지 않는다.

payout의 `cleared`는 공급자 미지급 수수료 잔액에서 정산된 금액이다. expected 입금은 cleared − 원천공제 − 지급 수수료다. 같은 통화일 때만 이 등식으로 자동 대사한다. 환전 지급은 원통화 cleared와 실제 지급 통화를 별도로 보존하고 환전 명세가 없으면 manual_review다.

cost_entries의 v1 paid 항목은 1회 현금 이동이다. 부분 지급은 지급분별 행으로 나누되 recognized_amount 합계가 원 비용을 초과하지 않게 source group을 검증한다. 발생 비용을 먼저 전액 기록한 경우 후속 지급 행의 recognized_amount는 0, cash_outflow만 반영한다. 환불·오류 정정은 signed 보상 행으로 이력을 보존한다. 기존 cost 연결은 source_key와 legacy_cost_id로 중복 배부를 방지한다.

## 5. 작업·승인·측정 객체

| 테이블 | 컬럼·제약 |
|---|---|
| jobs | id PK; kind!; job_key! UQ; payload_hash!; state!; attempt!; max_attempts!; next_attempt_at!; lease_owner?; lease_expires_at?; fence_token bigint!; result_ref?; correlation_id! |
| outbox | id PK; event_key! UQ; kind!; payload!; state! pending/sent/failed; attempts!; next_attempt_at!; sent_at? |
| approval_bindings | approval_id bigint PK/FK public.approvals; revision_id FK!; policy_version_id FK!; artifact_hash!; target!; action!; expires_at!; consumed_publication_id? |
| approval_events | id PK; approval_id FK!; update_key! UQ; actor_ref!; requested_transition!; result!; created_at! |
| publications | id PK; revision_id FK!; approval_id FK!; target!; idempotency_key! UQ; state!; artifact_hash!; git_commit?; external_deployment_id?; public_url?; verified_at? |
| click_events | event_id UUID PK; event_type! page_view/affiliate_click; link_id FK?; revision_id FK!; received_at!; occurred_at!; session_token?; qualification!; ingest_version! |
| pull_checkpoints | consumer_key text PK; cursor!; updated_at!; last_success_at!; last_error_code? |
| decision_runs | id PK; experiment_id FK!; input_snapshot_hash!; rule_version!; data_quality!; decision!; reasons!; generated_at!; UQ(experiment_id,input_snapshot_hash,rule_version) |

affiliate_click은 link_id 필수, page_view는 link_id null이다. link_id의 revision과 요청 revision이 일치해야 한다.

DB 역할별로 INSERT/UPDATE/DELETE를 제한한다. 원장·fact version·revision에 UPDATE/DELETE를 허용하지 않는 writer role을 사용하고 migration role만 DDL을 가진다. mutable pointer/state는 별도 서비스만 변경한다. jobs queue의 state와 public.executions의 감사 상태는 전이가 같은 트랜잭션에서 기록되도록 한다.

필수 인덱스: jobs(state,next_attempt_at), jobs(lease_expires_at), batches(account_id,report_family,captured_at), fact_versions(series_id,version_key), journal(account_id,economic_date), journal(fact_version_id), click_events(received_at), click_events(link_id,occurred_at), outbox(state,next_attempt_at). MVP 규모에서는 파티셔닝을 필수로 하지 않는다.

### 5.1 추가 무결성·상태 규칙

- import_batches.state는 received/normalized/quarantined/posted/stale/conflict/failed, data_quality는 available/partial/unavailable이다. normalized 이전에는 전기 불가, posted는 원장과 같은 transaction에서만 설정한다.
- jobs.state는 queued/running/retry_wait/succeeded/failed/manual_review/cancelled다. publications의 building/awaiting_approval 등 도메인 상태와 구분한다. jobs.attempt는 0 이상, max_attempts는 1 이상, running이면 lease_owner·expires_at 필수다.
- fact_series.currency는 생성 후 변경 불가. currency가 달라진 입력은 다른 합법적인 series로 계약화하거나 quarantine한다. 같은 series의 금액 통화는 모두 일치해야 한다.
- fact_series.current_version_id는 동일 series의 fact_versions만 참조하도록 복합 FK 또는 지연 constraint trigger로 검증한다. pointer에 다른 거래의 버전을 연결할 수 없다.
- journal entry의 account/series/version/currency 일치는 복합 FK와 전기 함수가 검증한다. delta=0은 원장 생성 없이 fact version만 보존할 수 있다.
- tracking_bindings는 content_id 또는 experiment_id 중 정확히 하나만 허용한다. content_id가 있으면 실험은 content_extensions에서 도출한다. timestamp 범위는 시작 포함·끝 제외이며 같은 계정·키의 범위 중첩을 DB constraint 또는 잠금된 검증 함수로 막는다.
- approval binding과 publication의 revision/target/artifact는 모두 같아야 한다. 한 승인 binding은 하나의 publication만 소비하며 그 publication의 재시도만 허용한다.
- cash_movements와 cost_entries의 증빙 키는 같은 현금 이동을 두 번 반영할 수 없도록 source 범위와 함께 검증한다. 기존 cost 연결이 있으면 legacy 자료와 신규 자료를 합산하는 조회를 금지한다.
- budget cap은 0 이상 또는 null. paid_at이 없는 cost 행은 cash_outflow를 null로 유지한다. 입금·비용 환불은 기존 행 수정 없이 원거래 reference를 가진 signed 보상 행을 쓴다.
- 공개 클릭은 money writer를 호출할 권한이 없다. 모든 production 객체 간 FK는 같은 environment의 account를 가리켜야 한다.

## 6. 수입·전기 알고리즘

### 6.1 원본 수입과 검증

1. private inbox의 파일 크기·형식·경로를 검증한다. 기본 20MB/100,000행 상한, 초과는 분할 또는 배치 작업으로 처리한다.
2. file hash·manifest·contract version으로 batch를 확보한다. 같은 파일의 같은 contract 재수입은 기존 결과를 반환한다.
3. 임시 staging에서 정규화한다. 헤더·상태·통화·키·행 합계의 오류가 있으면 batch를 quarantine한다. v1은 부분 성공 전기를 하지 않는다.
4. 요약행과 상세행을 분리한다. authoritative stream의 통화별 control total을 일치시킨다. 차이는 지정된 통화 scale로 설명돼야 하며 자동 epsilon 무시는 하지 않는다.
5. 오류가 없으면 정상화 버전과 원장 후보를 준비한다. 검토자가 승인한 contract 외의 키·상태 유추는 금지한다.

### 6.2 변경 보고와 중첩 기간

- 안정 주문항목 키가 있는 경우 같은 series_key의 새 version이 현재 누계 balance를 바꾼다.
- 일별 집계라면 series_key는 공급자 계정·날짜·추적키·상품·통화·보고 단위 등 계약상 전체 차원이다. 같은 날 집계를 다시 더하지 않는다.
- 보고서가 임의 기간 총계만 제공하면 겹치는 기간을 additive revenue로 사용할 수 없다. 동일한 canonical 비중첩 구간의 전체 snapshot으로만 수입하거나 겹침을 quarantine한다.
- 새 snapshot에서 행이 사라졌다고 0으로 간주하지 않는다. 공급자가 '완전 snapshot, 누락=삭제/0'을 보장하고 batch 전체 검증이 끝난 경우에만 명시적 tombstone version을 생성한다.
- 공급자 revision/updated_at으로 순서를 비교한다. 늦게 도착한 구버전은 원본 보존 후 stale로 남기고 현재 잔액을 되돌리지 않는다.
- revision이 없고 값이 다르면 수집 시각만으로 최신임을 확정하지 않는다. `replacement_verified` 증거와 승인된 effective ordering을 요구한다.
- 같은 version_key의 다른 content_hash는 conflict다. 자동 덮어쓰기하지 않는다.

### 6.3 트랜잭션과 동시성

계정 + authoritative family 단위의 잠금을 확보한 단일 전기 작업이 batch를 처리한다. 실제 구현에서는 DB transaction advisory lock 또는 lock row를 택하고 동일 규칙을 모든 writer에 적용한다. fact_series 행 잠금은 고정된 정렬 순서로 확보한다.

```text
BEGIN
  lock(account, family)
  verify batch normalized and not already posted
  for series in sorted order:
    lock series; read current version
    reject conflict/stale replacement
    insert immutable fact version
    calculate delta for each supplied bucket
    insert journal entries with unique source keys
    update current_version pointer
  mark batch posted
  insert outbox(batch_id + posted)
COMMIT
```

delta = 새 누계 − 이전 누계. 처음 공급되는 bucket의 baseline은 0이다. 누락된 bucket은 delta 없음. 새로운 parser가 기존 파일을 다시 해석해도 현재 series와 비교해 delta만 전기한다. 다른 키 정책으로 바뀌면 재키잉 migration 검토 없이 전기하지 않는다.

parser 수정으로 같은 공급자 version의 canonical 금액이 달라지는 경우도 기본적으로 conflict다. 근거를 검토한 수동 정정만 `correction:<approved-change-id>` version으로 받아 이전 version을 참조하고 차액을 전기한다. contract version 변경만으로 기존 중복 방지 키를 우회하지 않는다.

UQ source_key는 `series_id + accepted_version_key + bucket`이다. transaction 실패 시 원장·pointer·batch 상태를 함께 rollback한다. 외부 알림은 commit 뒤 outbox로 전달한다. email/Telegram의 중복 0 보장은 하지 않고 event key·전송 기록으로 재전송을 억제한다.

## 7. 상태별 금액과 귀속

pending balance는 미확정 예상 수수료다. confirmed cumulative는 취소·수정 포함 누적 확정 순수수료이며 payout 때문에 0으로 바뀌지 않는다. pending과 confirmed의 전이는 공급자 contract가 증명할 때만 연결한다.

원장의 합계:

```text
pending = SUM(journal.delta WHERE bucket=pending)
confirmed_net = SUM(journal.delta WHERE bucket=confirmed)
provider_receivable = confirmed_net - SUM(payout_adjustments.cleared_delta)
cash_received = SUM(cash_movements.signed_amount)
net_cash_flow = cash_received - SUM(cost_entries.cash_outflow)
contribution = attributable confirmed_net - attributable recognized direct costs
```

기존 review의 예처럼 지급 수수료가 순입금에서 이미 공제되면 cash_outflow로 한 번 더 차감하지 않는다. 공헌이익에서는 지급 수수료를 별도 직접비로 인식할 수 있지만 현금성 지출과 구분한다. 취소가 지급 후 발생하면 receivable이 음수가 될 수 있으며 다음 지급 상계·환수 대상으로 표시한다.

공제 수수료를 recognized cost로 기록할 경우 source_key는 payout ID + 정산 version + fee 구분으로 정한다. 동일 fee를 수동 cost와 자동 payout 비용으로 중복 인식하지 않는다. 원천공제는 비용인지 세금 관련 자산인지 내부 관리 정책과 회계 검토에 따라 분류하며 단순 운영비로 자동 처리하지 않는다.

수익의 근거 날짜(economic_date)와 언제 알게 됐는지(posted_at)를 모두 쓴다. '당시 보고값'은 posted_at cutoff로, '수정 반영 실적'은 최신 원장과 economic_date로 재계산한다. 두 화면의 차이를 오류로 숨기지 않는다.

정확한 귀속은 공식 tracking_key의 유효 mapping으로만 결정한다. 클릭 상품과 구매 상품 일치는 필수 조건이 아니다. 원장 attribution JSON은 level, content_id/experiment_id, binding_id, evidence_ref, mapping_version, reason을 가진다. 나중에 mapping이 보완되면 금액을 새로 벌었다고 전기하지 않고 별도 귀속 재분류 이력을 둔다. v1은 귀속 변경 이력을 `decision_runs`가 아니라 전용 `attribution_revisions`에 저장한다.

`attribution_revisions`: id PK, journal_entry_id FK!, version int!, mapping JSONB!, reason!, evidence_ref!, created_at!, UQ(journal_entry_id,version). 최초 journal attribution은 보존하고 최신 유효 revision을 조회한다. 재분류 후 콘텐츠 합계 변화와 전체 합계 불변을 테스트한다.

## 8. 합성 인수 데이터와 기대값

각 예시는 독립 테스트다. 별도 표시가 없으면 account=fixture-KRW, currency=KRW, environment=test다.

| ID | 입력 | 기대값 |
|---|---|---|
| F01 | series=S1 v1 pending=10000 confirmed=0; v2 pending=0 confirmed=10000 | pending delta +10000,-10000; confirmed +10000; 현재 pending 0, confirmed 10000 |
| F02 | F01의 동일 파일 재수입·새 파일에 같은 S1/v2 | 새 원장 0건, confirmed 10000 유지 |
| F03 | S1/v3 pending=0 confirmed=8000 | confirmed delta -2000, confirmed 합계 8000 |
| F04 | F03 뒤 payout P1 cleared=8000, fee=500, net_expected=7500; 입금 7500; 비용 현금 3000 | receivable 0, 입금 7500, 순현금 4500 |
| F05 | content A/B 모두 같은 item 추천, tracking 없음; confirmed 8000 | program_only 8000, A/B 확정 귀속 각각 null |
| F06 | A의 고유 tracking 반환, 다른 item 구매, confirmed 1200 | A content_exact 1200, 실제 구매 item 보존 |
| F07 | 일별 집계 K=day1 v1 3000, v2 2500; day2 1000. 중첩 보고 재수입 | 합계 3500; 3000+2500+1000으로 합산 금지 |
| F08 | 같은 S1/v3에 다른 confirmed 금액 또는 v2 지연 도착 | 충돌은 quarantine, 구버전은 stale, 현재 합계 불변 |
| F09 | detail 1000,2000과 summary 3000 동시 존재 | confirmed 3000, summary 추가 전기 0 |
| F10 | F04 후 추가 취소 1000 | confirmed 7000, cleared 8000, receivable -1000, 실제 cash 7500 유지 |
| F11 | raw 원본은 동일, parser v2 재처리 결과 동일 | provenance는 새 batch, 신규 경제 금액 delta 0 |
| F12 | 원장 8000을 program_only에서 content A로 재분류 | 전체 8000 불변, A 귀속 8000, 재분류 증거 보존 |

## 9. 조회 계약

신규 보고는 `affiliate.v_program_balances`, `v_content_economics`, `v_experiment_economics`, `v_cash_flow`, `v_data_readiness`를 사용한다. 뷰 이름은 구현 목표이며 이번에 생성되지 않았다.

각 결과에 currency, basis(pending/confirmed/cash), economic_period, data_as_of, completeness, attribution_level, source_batch_refs를 노출한다. 0분모는 null/N_A, 자료가 없으면 unavailable이다. 초기 모델에서는 통화를 섞은 합계를 반환하지 않는다. 공통 KRW 보고는 fx rate version이 있을 때 별도 결과로 제공한다.

CTR 세션 지표는 자체 page_view와 click이 같은 session_token 체계를 사용할 때만 계산한다. session 측정이 비활성이면 클릭 event count까지만 제공한다. GA4와 자체 click count를 합쳐 정확한 session CTR이라고 이름 붙이지 않는다.

## 10. 구현 전 남은 검증

- 실제 공급자 report grain·키·정정 순서·상태 매핑 확보.
- 참조 FK의 계정·콘텐츠 일치, 격리 테스트 DB DDL compile 검증.
- 승인·publication·content revision 관계는 [05](05-publishing-and-measurement.md)와 공동 검증.
- 기존 public 테이블이 가진 제약과 extension의 쓰기 역할 검증.
- 실제 운영 migration·권한·데이터 보존은 [06](06-acceptance-and-runbook.md)의 적용 게이트 통과 후 수행.

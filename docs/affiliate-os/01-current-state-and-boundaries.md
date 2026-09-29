# 01. 현행 상태·경계·재사용 매핑

기준일 2026-09-13 · 패키지 v1.0 · 관련 이슈 R03/R05/R06/R11/R12

## 1. 읽기 전용 관찰 결과

사전 점검에서 n8n health 응답, PostgreSQL 연결, 세 컨테이너 실행을 확인했다. Ollama 모델 목록에 `qwen3.5:4b`가 있다. 모델의 응답 품질·복원 성공·새 제휴 흐름 완성은 확인하지 않았다. 최근 실패 목록에 fallback SyntaxError가 있지만 현재 장애 지속 여부는 이번에 진단하지 않았다.

DB `n8n`의 `information_schema.columns`와 일부 `pg_constraint`를 조회했다. 계정·주문·개인정보 레코드나 비밀값은 수집하지 않았다. 다음 표는 실제 존재하는 객체와 코드 참조에 기반한다.

| 기존 객체 | 실제 계약·소비자 | 신규 설계 처리 |
|---|---|---|
| `public.content` | bigint ID, channel, body_ref, metadata, published_url, status | ID·조회용 요약 재사용. 불변 상업 revision은 별도 저장 |
| `public.experiments` | business_idea_id, target_value, result, planned/running/paused/completed/cancelled | 관리 ID 재사용, 신규 확장 테이블을 1:1 연결 |
| `public.assets` | 콘텐츠의 asset FK 대상 | 기존 ID 그대로 참조, 임의 재번호 없음 |
| `public.approvals` | approval_key UNIQUE, status CHECK, decided_by, metadata | 신규 상업 승인 결과의 단일 상태 저장소로 선택 |
| `public.approval_requests` | request_type, risk_level, estimated_cost, status. asset FK는 `digital_assets` | 기존 게시 승인용. 새 승인과 동일 테이블로 간주하지 않음 |
| `public.revenue_autopilot_jobs` | approval_request_id → approval_requests, content_id → content | 기존 게시 작업 전용. 새 revision을 자동 유입시키지 않음 |
| `public.revenue` | amount >= 0, status estimated/reported/settled/reversed, asset FK | 기존 수익 유지. 신규 signed adjustment 원장과 합산 금지 |
| `public.cost` | 단수명, amount >= 0, occurred_on, vendor, evidence_ref | 기존 비용 자료 연결 가능. paid_at이 없어 현금성 판단은 증거 추가 필요 |
| `public.revenue_channel_metrics` | 일별 content·channel·source 집계, 숫자 기본값 0 | 레거시 집계 유지. 신규 품질 상태·현금 보고의 원본으로 사용하지 않음 |
| `public.executions`, `agent_actions` | 실행·조치 감사 | 신규 job의 correlation ID와 연결, 상태 책임은 신규 jobs |

`approval_requests.asset_id`와 `content.asset_id`는 각각 다른 asset 테이블을 참조한다. 숫자가 같다는 이유로 결합하면 안 된다. 신규 approval은 request 테이블의 asset 키를 가져오지 않고 revision binding으로 대상과 연결한다.

저장소 SQL 검색에서는 `approval_requests` 생성문을 찾지 못했고 migration 009의 FK 참조는 존재했다. 따라서 기존 migration 묶음만으로 빈 DB 전체를 재현할 수 있다고 가정하지 않는다. I01의 public fixture는 테스트 전용 최소 계약이며, 실제 운영 복원 명세와는 별도로 관리한다.

## 2. 코드로 확인한 기존 게시 경로

[Publisher](../../tools/autopilot-publisher.py)는 `BRANCH=feat/atemoya-ops-baseline`, GitHub Pages BASE_URL을 상수로 사용한다. 현재 조사 브랜치는 `feat/atemoya-publication-record`여서 이 체크아웃에서 기존 Publisher를 실행하면 브랜치 검사가 거절할 수 있다. 실제 LaunchAgent가 어느 복제본을 사용하는지까지 확인하지 않았으므로 운영 장애로 단정하지 않는다.

기존 경로는 approved job 선택 → 렌더링 → 사이트 검사 → 일부 파일 커밋·push → branch_ready → 공개 URL HTTP 200 감지 → published다. 공개 감지 함수에서 기대 본문 revision/hash 대조는 확인되지 않았다.

[Reconciler](../../tools/revenue-ops-reconciler.py)는 `approval_requests`에서 job stage를 갱신한다. 신규 승인 상태를 이 테이블에 복사해 두 흐름이 동시에 소비하게 만들지 않는다.

[Pages workflow](../../.github/workflows/pages.yml)는 main push/수동 실행으로 동작하며 저장소 루트 `.`를 업로드한다. 또한 사이트 검사 후 `configure-site.mjs`로 링크·분석 설정을 주입한다. 신규 상업 배포에서는 다음 순서로 바꿀 필요가 있다.

`정해진 revision 렌더링 → 설정·링크 확정 → 최종 검사 → manifest 서명/승인 확인 → 공개 전용 디렉터리 배포`

저장소 루트를 공개 아티팩트로 쓰면 설계·운영 문서까지 포함될 가능성이 있다. 이번 상세 설계 파일은 로컬 미커밋 문서이고 배포되지 않았다. 이후 이 문서를 Git에 반영할 때도 기존 루트 업로드 문제를 검토하고 공개 산출물 allowlist를 먼저 정해야 한다.

## 3. 목표 경계

```text
공개: 정적 HTML·이미지·검색 메타데이터
  ├─ 브라우저 → 공급자 공식 제휴 URL (직접 이동)
  └─ 브라우저 → /events/v1 → 외부 수집 저장소

제한된 기계 간 접근:
  iMac pull worker → export API → 수집 이벤트 → PostgreSQL
  게시 worker → 운영 호스팅 API

비공개: n8n 관리·PostgreSQL·원본 정산서·승인·credential reference
```

공개 수집기 후보는 Cloudflare Worker + D1, 정적 사이트 후보는 Workers Static Assets다. 기능을 확인한 기술 제안이며 계정·가격·상업 이용 조건·데이터 처리 지역은 운영 배포 전에 확정한다. 제품 API의 세부 배포 명령은 이번 단계에서 고정하지 않는다.

Cloudflare는 Worker와 정적 자산을 함께 배포하는 기능을 문서화한다. 이 기능은 host adapter 후보 선택의 근거이며 신규 계정 생성이나 무료 운영 보장이 아니다. [공식 문서](https://developers.cloudflare.com/workers/static-assets/), 확인 2026-09-13.

공급자와 호스팅은 다른 개념이다. 수익 파트너 변경은 offer/report adapter를 바꾸고, 호스팅 변경은 deployment/event-store adapter만 바꾼다.

## 4. 쓰기 소유권

| 데이터/행동 | 유일한 쓰기 주체 | 읽는 주체 |
|---|---|---|
| 원본 보고 파일 | import loader | parser, 검토자 |
| 정규화 fact version | normalizer | reconciler |
| 수수료 원장 | posting service | 보고·판정, 조회 전용 |
| 승인 상태 | direct user instruction 또는 legacy approval service | publisher |
| 공개 revision | 신규 publisher, 소유권 등록 후 | 웹 방문자 |
| 클릭 원시 이벤트 | edge collector | 인증된 pull worker |
| 운영 click table | pull worker | 분석 |
| 경영 결정 | 사용자 상시 지시 + 규칙 엔진 기록 | 실행 스케줄러 |

AI는 SQL·배포 credential을 받지 않는다. 사용자의 상시 지시는 직접 게시 권한으로 기록하되, AI가 임의로 권한을 확장하지 않는다. n8n은 예약과 작업 요청을 담당하고 수입·원장 불변조건은 테스트 가능한 모듈로 분리한다.

## 5. 기존 경로와 신규 경로의 공존

DESIGN: 신규 `affiliate.content_extensions`가 관리하는 콘텐츠는 신규 전용 콘텐츠다. 첫 구현에서는 기존 content ID를 자동 등록하지 않는다. 이미 `revenue_autopilot_jobs`에 등장하는 content ID의 신규 등록은 차단한다.

기존 콘텐츠를 이전해야 할 경우 전용 migration으로 다음을 함께 검증한다: 기존 큐 활성 작업 없음, 기존 스케줄의 재등록 방지, 새 publication ownership, 원본 URL 이력. 삭제·상태 변경을 승인 우회 수단으로 사용하지 않는다. asset 수준 연결이 필요하면 별도 검증된 mapping을 만든다.

신규 수익을 기존 Guardian이 읽을 수 없는 기간에는 `affiliate_scope_not_integrated`로 표시할 계획이다. 신규 원장 전체를 `public.revenue`에 복사하는 임시 해결책은 사용하지 않는다. 이후 대시보드 소비자를 신규 명시적 뷰로 단계적으로 전환한다.

## 6. 마이그레이션·복구 설계

1. 실제 schema·constraint·index·consumer 목록을 비밀 없는 형태로 스냅샷하고 baseline과 비교한다.
2. 격리 DB에서 `affiliate` schema와 신규 객체를 생성한다. 운영은 아직 변경하지 않는다.
3. FK 참조 대상인 public 테스트 테이블에 합성 레코드를 넣어 회귀 테스트한다.
4. 신규 소비자 feature flag 기본 off, schema 버전 검사 필수.
5. 운영 적용 시 백업·복원 증거, DB 권한, 배포 승인 조건을 확인한다.
6. 롤백은 신규 작업 중지·소비자 구버전 복귀다. 이미 기록한 정산 원장은 drop/delete하지 않는다. 잘못된 전기는 보상 원장으로 정정한다.

현재 확인 범위에는 전체 migration 재현, 실제 복구 훈련, 역방향 프록시 설정, 외부 모니터, 호스팅 계정 승인이 포함되지 않는다. 관련 출시는 [06](06-acceptance-and-runbook.md)의 G2 조건으로 관리한다.

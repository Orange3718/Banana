# 05. 게시·승인·클릭 측정 계약

v1.0 · DESIGN · R03/R04/R05/R06/R10/R12

## 1. 공개 API와 내부 API

| 경로 | 접근 | 기능 |
|---|---|---|
| `POST /events/v1` | 공개, rate/size/schema 제한 | page_view·affiliate_click 수집 |
| `GET /internal/events/v1/export` | collector_read 서비스 자격 | 미수입 이벤트 페이지 조회 |
| `POST /internal/events/v1/ack` | collector_read 서비스 자격 | PostgreSQL 저장 완료 batch 확인 |
| `POST /internal/imports/v1` | 운영망 import_operator | private 파일 참조 수입 요청 |
| `POST /internal/approvals/v1/decision` | legacy 호환용 | 기존 승인 결과 반영; 신규 affiliate 게시에는 필수 아님 |
| `POST /internal/publications/v1` | publisher 서비스 | 승인 revision의 배포 job 생성 |
| `GET /internal/jobs/v1/{id}` | 운영 조회 역할 | 상태·결과·마스킹 오류 확인 |

`internal`이라는 경로 이름 자체는 접근 통제가 아니다. edge export/ack는 별도 서비스 인증, 운영 API는 사설 네트워크·서버 권한 검사 둘 다 적용한다. 공개 사이트에서 내부 운영 API와 n8n 편집기·DB에 연결하지 않는다.

## 2. 공개 이벤트 계약

요청 예시는 합성 값이다. 최대 2KB, `Content-Type: application/json` 또는 JSON을 담은 `text/plain`만 허용한다. 허용하지 않은 필드·중첩 구조·스크립트 데이터는 400으로 거절한다.

```json
{
  "schema_version": 1,
  "event_id": "00000000-0000-4000-8000-000000000001",
  "event_type": "affiliate_click",
  "revision_id": "00000000-0000-4000-8000-000000000002",
  "link_id": "00000000-0000-4000-8000-000000000003",
  "occurred_at": "2026-09-13T06:00:00Z",
  "session_token": null,
  "measurement_policy_version": "measure-v1"
}
```

응답: 내구성 저장에 성공하면 202와 event_id. 동일 ID·동일 payload는 202 duplicate, 동일 ID·다른 payload는 409. 입력 오류 400, 과대 413, 빈도 초과 429, 저장소 오류 503. 202는 유효 사용자임을 인정하거나 수익을 기록했다는 뜻이 아니다.

검증 규칙:

- event_id·revision_id·link_id는 UUID 구문 검증, manifest에 있는 revision·link 관계 대조.
- page_view는 link_id null; click은 link_id 필수. 공개 중인 revision 또는 허용된 과거 revision만 수집한다.
- occurred_at은 서버 received_at 기준 미래 5분·과거 24시간 범위를 기본값으로 하되, 범위 밖 사건은 원장과 섞지 않고 reject reason에 기록한다. 분석은 서버시각도 보존한다.
- session_token은 nullable, 최대 64자 임의 ID다. 실제 사람·계정 ID를 사용하지 않는다. 세션 측정을 허용하는 정책일 때만 30분 비활성 만료의 first-party 토큰을 생성한다.
- 첫 정책이 세션 측정을 허용하지 않으면 session_token은 항상 null이고 CTR은 N/A다. 단순 클릭 건수만 집계한다.
- payload에는 계정번호, 금액, 구매자, 전체 referrer, IP, 사용자 입력 URL을 받지 않는다.

브라우저는 정상 anchor href의 공급자 발행 링크를 유지하고 event handler에서 `sendBeacon` 또는 keepalive 요청을 보낸다. 클릭 이동을 막거나 응답을 기다리지 않는다. JavaScript 비활성 상태에서도 제휴 링크가 동작해야 한다. 전송 재시도 실패에 대해 사용자에게 팝업·오류 화면을 띄우지 않는다.

## 3. 악용 방어·저장·손실 처리

초기 제안값: 네트워크 단위 60 events/min, site 전체 10,000 events/day, body 2KB. 구현·부하 검사 후 조정하며 실제 고객 트래픽 상한으로 오해하지 않는다. shared NAT 영향은 별도 점검한다. 공급자 rate limit 기능은 위치·동시성에 따라 강한 전역 비용 상한을 보장하지 않을 수 있어 서비스별 과금 상한과 별도로 관리한다.

Origin 허용 목록·manifest 검증·rate limit·중복·봇 분류를 함께 사용한다. 이는 공개 이벤트 위조를 완전히 막지 못한다. 클릭은 관측 데이터이고 공급자 수수료 보고가 재무 근거다. 원시 IP가 edge 보안 로그에 기록될 수 있으므로 payload를 최소화해도 개인정보 검토가 끝난 것으로 보지 않는다.

collector의 저장소는 PostgreSQL 수입 전 전달 버퍼다. canonical 운영 이벤트는 PostgreSQL이 가진다. 권장 구현은 edge Worker/D1 또는 같은 내구성 계약을 만족하는 대체 저장소다. [D1 한도 문서](https://developers.cloudflare.com/d1/platform/limits/)를 계정·용량 설계에서 확인한다. 무료 무제한 저장을 가정하지 않는다.

### 전달 계약

1. collector는 immutable event_id와 payload hash로 저장한 뒤 202를 보낸다.
2. pull worker가 5분 간격 제안 주기로 export를 요청한다. 서버는 아직 ack되지 않은 사건을 최대 500개 묶어 export_batch_id·checksum·event_count로 반환한다.
3. 같은 export_batch_id 재요청은 같은 내용을 반환한다. 여러 consumer가 생겨도 하나의 active consumer_key만 해당 stream을 소유한다.
4. PostgreSQL에 event_id UQ로 insert하고 batch 체크포인트를 같은 transaction에서 commit한다.
5. commit 이후에만 ack한다. ack 실패 시 같은 batch 재전송을 허용하고 PostgreSQL에서 중복 제거한다.
6. export batch 생성 시점 후 도착한 사건은 이후 batch에 포함된다. received_at cursor만으로 건너뛰지 않는다.
7. collector는 ack된 이벤트를 7일 후 삭제하는 기본 제안, 미ack 이벤트는 최대 30일 보존한다. 만료 전 24시간 경보를 보내고 강제 만료된 수량·구간을 gap record로 남긴다.

export/ack 인증은 브라우저에 없는 별도 서비스 자격, read/ack 범위만 부여한다. 배포 자격과 공유하지 않는다. query string에 토큰을 넣지 않는다. full URL·payload의 기본 로그 기록을 금지한다.

PostgreSQL 원시 이벤트는 30일, 집계는 13개월 초기 제안이다. 그보다 긴 dedup marker가 필요하면 이벤트 hash를 별도 보존하되 개인정보 분류·보존 범위를 함께 결정한다. 오래된 batch 재수입은 보존 정책과 replay window를 검증해 허용하며 이미 만료된 기간을 정상 신규 클릭으로 더하지 않는다.

## 4. 콘텐츠·아티팩트·승인

DB `content_revisions.body_text`와 evidence가 불변 초안 원본이다. Git은 템플릿·정책·빌드 코드의 원본과 검토할 release artifact를 보관한다. Git에서 결과 HTML을 직접 수정하면 새 revision으로 역반영 후 다시 승인해야 한다.

build manifest 필수: revision_id, body_hash, template_version, policy_version, link_manifest_hash, target, git_commit, artifact_hash. revision의 affiliate_url을 확정한 뒤 고지·링크·검색 metadata·문자열 escaping·이미지 권리 검사를 수행한다.

직접 게시 모드에서도 대상은 원문만이 아니라 target·정책·확정 링크를 포함한 최종 artifact hash다. 게시 전 hash·QA·allowlist·중복 키를 검증하고, 변경된 artifact는 새 publication으로 기록한다.

기존 `public.approvals` binding은 legacy 작업에만 사용한다. 신규 affiliate publication은 `authorization_mode=direct_user_instruction`으로 사용자 상시 지시를 참조하고, 실행마다 artifact hash·정책·QA·allowlist를 기술적으로 검증한다.

Telegram 수신기는 기존 회사 봇의 webhook을 새로 등록해 대체하지 않는다. 현재 수신 흐름 내부에서 명시적인 신규 namespace 요청만 승인 어댑터로 전달한다. chat_id·from.id allowlist와 update_id 중복을 서버에서 확인한다. 채팅방에 있다는 사실만으로 승인자를 인정하지 않는다.

기존 Telegram 승인 명령 형식은 legacy publisher에만 적용한다. 신규 affiliate direct publication은 사용자의 상시 지시를 authorization_mode로 기록하고 별도 승인 메시지를 생성하지 않는다.

## 5. 게시 job 상태

```text
queued → building → ready → deploying → verifying → published
             └→ qa_failed             └→ manual_review
                                              └→ retry_wait / manual_review
```

publication의 idempotency_key는 SHA256(revision_id,target,artifact_hash,action)다. 같은 key의 같은 payload 요청은 기존 job 반환, 같은 key 다른 payload는 409다.

dispatch 트랜잭션은 authorization_mode, content ownership, 정책, 현재 target, QA 결과를 재검증한다. 동일 idempotency key만 재시도하며 새 revision·다른 target은 새 publication으로 만든다.

lease는 10분, heartbeat 30초, 최대 3회 자동 시도 초기값이다. 유효 lease가 있어도 외부 side effect 전 fence_token 확인을 한다. 배포는 idempotency 지원 host 기능을 사용하거나 deterministic deployment reference로 기존 결과를 조회한다. host가 둘 다 지원하지 않으면 timeout 후 무조건 재배포하지 않고 manual_review다.

외부 배포 성공 → DB 실패에서는 외부 deployment ID와 artifact hash를 조회해 동일 결과를 확정하고 DB 상태만 복구한다. 200 응답만으로 성공을 판단하지 않는다. HTML revision marker, 공개 manifest hash, canonical, 고지·링크, redirect destination을 확인한다.

정적 파일은 공개용 `dist-public/` allowlist만 업로드한다. docs·SQL·원본 보고·credential reference·Git 메타데이터는 공개 산출물에 포함하지 않는다. release 완료 전 아티팩트 파일 목록을 검사한다.

## 6. 재시도와 복구

| 원인 | 동작 |
|---|---|
| HTTP 429 | Retry-After를 존중, 최대 시도·예산 내 재시도 |
| 네트워크·5xx | 30초/2분/10분 기반 지연과 jitter; side effect 결과 조회 우선 |
| 401/403 | 자동 반복 중지, credential/권한 점검 요청 |
| 승인·정책·hash 불일치 | 재시도 금지, 새 승인 또는 재검토 |
| 보고서 schema 오류 | quarantine, 원본 보존 |
| DB deadlock/일시 연결 실패 | 전체 transaction 재시도, UQ로 중복 방지 |
| iMac 중단 | 공개 사이트·링크 유지, collector 버퍼 후 복구 pull |

일반 retry 최대 3회는 최초 시도를 포함한다. 승인이 이미 검증되어 배포가 시작된 후 만료됐더라도 기존 외부 결과 확인은 허용하되 새로운 배포는 새 승인 정책에 따른다.

롤백은 직전 검증된 artifact로 target을 되돌리는 별도 action이다. 이전 artifact가 현 정책을 충족하는지 확인한다. 정책 위반 페이지의 긴급 비공개는 승인된 운영 권한과 런북에 한정하며 문서를 썼다는 이유로 자동 실행 권한이 생기지 않는다.

## 7. QA와 모델 경계

deterministic QA: 스키마, 필수 고지, link allowlist·발행 형식, 모든 revision/hash, HTML escaping, placeholder·민감 문자열·공개 파일 목록.

사실 QA: claim별 근거·확인일·시장·가격/시간 유효성·비교 근거·실제 경험 여부. 모델 평가 30개 합성 사례와 첫 3–5개 글의 독립 검토 결과를 저장한다. 동일 모델의 자기 평가 점수만으로 approval을 만들지 않는다.

모델의 context는 근거 묶음과 필요한 입력으로 제한한다. 게시·원장·승인 tool을 주지 않으며 외부 글에 포함된 지시를 실행하지 않는다. reasoning 결과와 원본 출처는 기록하되 비밀·구매자 개인정보를 프롬프트로 보내지 않는다.

이 파일은 endpoint·상태·권한의 구현 명세다. 실제 API 서버·collector·예약 작업은 다음 구축 단계에서 작성하고 검증한다.

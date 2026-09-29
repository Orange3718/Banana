# Atemoya Vault Linker — 설계문서

작성일: 2026-09-28

목적: Obsidian(AtemoyaVault)의 노트 연결고리를 찾고, 이 시스템에서 "서브
에이전트"가 어떻게 돌아가는지 정리한 문서. As-Is(지금 실제로 도는 것)와
개선 방향을 운영 관점에서 구분한다.

---

## 1. As-Is — 지금 실제로 있는 것

### 1.1 Obsidian Vault 실제 상태

`~/AtemoyaVault`에는 **노트 3개, 위키링크 2개**뿐이다.

| 노트 | 역할 | 나가는 링크 |
| --- | --- | --- |
| `Atemoya Home.md` | 허브 | → Inbox, Inbox 수집 기준, **Connections**(신규) |
| `00 Inbox/Atemoya Inbox.md` | PostgreSQL에서 15분마다 자동 갱신되는 대시보드 | 없음 |
| `10 Operations/Inbox 수집 기준.md` | 수집 기준 설명 | 없음 |

`Atemoya Inbox.md`는 `business_ideas`·`approvals`·`executions(failed/retrying)`
3개 섹션만 보여주는데, 지금은 앞의 두 테이블이 **0행**이라 전부 "없음"으로
찍힌다. 즉 링크를 만들 노트 콘텐츠 자체가 거의 없었다.

### 1.2 실제로 쌓여 있는 운영 데이터 (링크의 재료)

| 테이블 | 실제 행 수 (COUNT(\*) 기준) | 용도 |
| --- | ---: | --- |
| `source_observations` | 1,310 | HN·Reddit·Google News 등 공개 수집 원문 |
| `local_llm_runs` | 545 | 로컬 Qwen 조사·초안 실행 기록 |
| `affiliate.publications` | 11 | 실제 게시된 쿠팡 콘텐츠 |
| `affiliate.jobs` | 10 | 게시 대기열 |
| `business_ideas` | 0 | (비어 있음) |
| `content` | 0 | (레거시 Revenue Autopilot 경로, 비어 있음 — 실제 게시는 `affiliate.*`로 이동함) |

`pg_stat_user_tables.n_live_tup`은 통계 갱신이 안 돼 위 테이블 전부 0으로
잘못 표시한다 — 운영 점검 시 이 통계 컬럼을 그대로 믿지 말고 `COUNT(*)`로
재확인해야 한다.

### 1.3 기존 "서브 에이전트" 운영 패턴 (n8n)

이 시스템에서 자율적으로 도는 단위는 n8n 워크플로다. `AtemoyaOpsGuardian01`,
`AtemoyaRevenueAutopilot01` 등을 분석한 결과 하나의 일관된 하우스 패턴이 있다.

```
scheduleTrigger ─┐
                  ├─→ postgres(작업 조회/점유) ─→ code(프롬프트 구성)
webhook(수동실행) ─┘         │
                             ▼
                   httpRequest → 로컬 Ollama qwen3.5:4b
                   (http://host.docker.internal:11434/api/chat)
                             │
                             ▼
                   code(파싱 + 결정적 QA) ─→ postgres(결과 저장)
                             │
                             ▼ (필요할 때만)
                          telegram
```

핵심 운영 원칙(모든 기존 워크플로가 지킴):
- **판정은 코드/규칙이 하고, 로컬 모델은 설명·요약만 한다.** 프롬프트에
  "판정을 바꾸지 마라", "없는 사실을 만들지 마라", "사용자 승인을 요청하지
  마라"가 명시적으로 들어간다.
- Postgres credential은 전부 `AtemoyaPostgresMemory01` 하나를 공유한다.
- 새 워크플로는 **import 후 비활성 상태로 두고, Owner 검토 후에만 활성화**
  한다 (`docs/ATEMOYA_SYSTEM_BASELINE.md` 복구 순서 6번).

### 1.4 이번에 새로 만든 것

| 구성요소 | 상태 | 파일 |
| --- | --- | --- |
| `vault_links` 테이블 | **적용됨** (라이브 DB에 존재) | `db/migrations/016_vault_links.sql` |
| `AtemoyaVaultLinker01` n8n 워크플로 | **import됨, 비활성** — Owner 승인 대기 | `n8n/workflows/exports/AtemoyaVaultLinker01.json` |
| `export-obsidian-links.sh` + LaunchAgent `com.atemoya.obsidian-connections` | **로드됨, 매시간 실행 중** (로컬 전용, Git 미포함) | `ops/scripts/export-obsidian-links.sh` |
| `10 Operations/Atemoya Connections.md` | **생성됨**, 현재 "아직 없음" (링커 비활성이라 정상) | AtemoyaVault 내부 |

`AtemoyaVaultLinker01`은 위 하우스 패턴을 그대로 따른다: 매일 05:10 KST(+수동
웹훅)에 최근 14일 미연결 `source_observations`/`local_llm_runs`를 최대 50건
모아 로컬 Qwen에게 "확실한 관련 쌍만" 판단시키고, **원래 후보 목록에 없는
항목을 참조하면 무조건 버리는** 안전 검증을 거쳐 `vault_links`에 저장한다.
두 code 노드는 Node.js로 목업 입력을 직접 실행해 검증했다(정상 관계는
저장되고, 모델이 존재하지 않는 인덱스를 참조하면 버려지는 것까지 확인).

### 1.5 지금의 한계 — 솔직하게

**아직 진짜 위키링크 그래프가 아니다.** `source_observations`/`local_llm_runs`
개별 항목이 각자 Obsidian 노트 파일로 존재하지 않아서 `[[...]]`가 가리킬
대상이 없다. `export-obsidian-links.sh`는 지금 평문 목록(`- 항목A <-> 항목B —
이유`)을 렌더링할 뿐, Obsidian 그래프 뷰에는 아무 것도 안 뜬다.

---

## 2. 개선 방향

우선순위 순으로 정리한다. 전부 이번 세션에서 구현하지 않았고, 다음
세션이나 Owner 승인 뒤 진행할 항목이다.

### 2.1 (즉시 가능) n8n 워크플로 활성화

`AtemoyaVaultLinker01`을 n8n UI에서 검토하고 활성화하면, 다음 날 05:10
KST부터 실제 관계가 쌓이기 시작한다. 코드 수정이 필요 없는, 순수 Owner
결정 단계다.

### 2.2 Phase 2 — 항목별 노트 생성 (진짜 위키링크로 전환)

지금은 관계를 "평문 목록"으로만 보여준다. 진짜 그래프 뷰가 필요하면:

1. `source_observations`/`local_llm_runs`의 최근 N건을 각각 개별 노트
   파일로 생성하는 스크립트가 필요하다 (예: `20 Sources/<id>-<slug>.md`,
   `30 Runs/<run_key>.md`).
2. `export-obsidian-links.sh`가 관계를 평문이 아니라 해당 노트로의
   `[[20 Sources/101-ai-hardware|...]]` 위키링크로 바꿔 쓴다.
3. 노트 개수가 계속 늘어나므로 보존 기간(예: 90일 지난 노트 아카이브
   또는 삭제) 정책이 같이 필요하다 — 무한정 쌓이게 두면 Vault가 비대해지고
   Obsidian 그래프 뷰도 알아보기 어려워진다.

이건 새 스크립트 + 저장 정책 설계가 필요한 별도 작업으로, 지금 범위 밖이다.

### 2.3 관계 유형 확장

지금은 `same_topic`/`based_on`/`led_to` 3종류만 허용한다. 실제로 쓸모
있으려면 다음이 더 가치 있을 수 있다:

- **`content`가 어떤 `source_observations`를 근거로 썼는지** — 지금
  `affiliate.publications`와 `source_observations`를 잇는 관계는 후보에도
  없다(SQL이 두 테이블만 본다). 실제 "이 아이디어가 돈이 됐는가"를
  추적하려면 `affiliate.publications`/`affiliate.jobs`까지 후보에 넣어야
  한다.
- **재시도 관계** — 같은 주제가 `local_llm_runs`에서 여러 번 실패/재시도됐다면
  그 체인을 잇는 게 "왜 이 주제가 계속 막혔는가"를 보여주는 데 더 유용할
  수 있다.

### 2.4 운영 비용·안전 여유

- 매일 최대 50건 × 1회 Ollama 호출이라 로컬 리소스 부담은 작다(기존
  `local-llm`이 매시간 2건씩 도는 것과 비교해 훨씬 가볍다).
- 다만 `source_observations`가 매시간 늘어나므로(현재 1,310건, 계속 증가),
  "최근 14일·50건" 상한이 시간이 지나면 백로그를 다 못 따라잡을 수 있다 —
  몇 주 뒤 `vault_links` 적재 속도와 미연결 잔여 건수를 점검해서 상한을
  조정할지 판단한다.

---

## 3. 운영 관점 — 무엇을, 어떻게 확인하는가

### 3.1 지금 상태 확인

```bash
# vault_links에 뭐가 쌓였는지
docker exec atemoya-postgres sh -lc \
  'psql -X -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select count(*), max(created_at) from vault_links"'

# Connections 노트가 최근에 갱신됐는지
launchctl list | grep obsidian-connections
tail -20 ~/Library/Logs/Atemoya/obsidian-connections.log
```

### 3.2 활성화 절차 (Owner)

1. n8n 편집기(`https://orange-imac.tail14202a.ts.net/`)에서
   `AtemoyaVaultLinker01` 워크플로를 연다.
2. 노드별 프롬프트·SQL을 검토한다(이 문서 1.4·1.5절과 워크플로 JSON이
   일치하는지 확인).
3. 문제없으면 활성화(Active 토글). 이후 매일 05:10 KST에 자동 실행되고,
   `atemoya-vault-linker-run` 웹훅으로 수동 실행도 가능하다.

### 3.3 실패 모드

- **n8n 실행 실패**: `AtemoyaOpsGuardian01`의 `v_atemoya_recent_failures`
  뷰에 잡힌다(다른 워크플로와 동일 경로로 모니터링됨). 별도 알림 경로를
  새로 만들지 않았다.
- **로컬 Ollama 응답이 JSON이 아님**: `link-parse-qa` 코드 노드가
  `match(/\[[\s\S]*\]/)`로 배열만 추출하고, 실패하면 빈 배열을 반환한다 —
  워크플로가 에러로 죽지 않고 조용히 "이번엔 관계 없음"으로 끝난다.
- **모델이 관계를 지어냄**: `allowedIds` 셋에 없는 항목을 참조하면
  무조건 버린다(코드로 검증, 3절 참고 — 이미 시뮬레이션 테스트 통과).

---

## 4. 관련 문서

- `docs/ATEMOYA_SYSTEM_BASELINE.md` — "Obsidian Inbox bridge" 절에서 이
  문서를 가리킨다.
- `docs/OPEN_ITEMS.md` — 2026-09-28 항목이 이 작업의 최초 변경 이력이다.

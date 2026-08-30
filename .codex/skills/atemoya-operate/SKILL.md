---
name: atemoya-operate
description: Operate and extend the Atemoya AI-operated revenue system on the iMac. Use for every Atemoya status check, automation change, n8n/PostgreSQL/Ollama/Telegram task, source collection, affiliate-content workflow, publishing workflow, incident diagnosis, or request to continue unfinished work. It prevents repeated user questions by loading the project baseline, checking live state, resuming the highest-priority unfinished task, verifying end-to-end delivery, and reporting only evidence-backed outcomes.
---

# Atemoya 운영

## 시작 절차

1. 저장소를 `/Users/orange/Developer/Banana-atemoya-ops`로 고정한다.
2. `scripts/preflight.sh`를 실행해 Git, Docker, n8n, Ollama, LaunchAgent, 최근 DB 상태를 짧게 확인한다.
3. 반드시 다음 파일만 먼저 읽는다.
   - `docs/ATEMOYA_SYSTEM_BASELINE.md`
   - `docs/OPEN_ITEMS.md`
   - `references/operating-contract.md`
4. 현재 요청과 직접 관련된 문서만 추가로 읽는다. 긴 대화 전체를 다시 요약하지 않는다.
5. 미완료 작업을 `docs/OPEN_ITEMS.md`와 실제 시스템 상태로 대조하고, 안전하게 실행 가능한 다음 단계부터 바로 진행한다.

## 기준

- 최우선 목표는 수익과 순현금흐름이다.
- GitHub는 코드·스키마·워크플로의 기준점이고 PostgreSQL은 실행 상태의 기준점이다.
- n8n은 오케스트레이션, Ollama `qwen3.5:4b`는 기본 로컬 추론, Telegram은 결과·오류·승인 채널이다.
- 간단하고 반복적이거나 오래 걸리는 초안·분류·요약은 로컬 모델에 맡긴다.
- 최신 사실 수집은 공개 API/RSS/웹 수집기가 담당하며, 로컬 모델이 검색한 척하지 못하게 한다.
- Gemini 등 외부 API는 무료 범위의 보조 경로만 사용한다. OpenAI API 호출을 새로 추가하지 않는다.
- 비밀값을 Git, 문서, Telegram, Obsidian에 기록하지 않는다.

## 완료 계약

기능 하나가 동작한 것만으로 완료라고 말하지 않는다. 요청에 필요한 전체 흐름을 확인한다.

`수집 → 근거 저장 → 로컬 추론 → 결과 저장 → QA → Telegram → 승인 게이트 → 게시 → 게시 URL → 측정`

- 적용되는 마지막 단계까지 실제 증거를 확인한다.
- 예약 작업은 LaunchAgent/n8n 활성 상태와 최근 실행을 함께 확인한다.
- 백그라운드 실행으로 등록하지 않은 일을 `진행 중`이라고 표현하지 않는다.
- 계정 인증·2FA·결제·법적 동의가 유일한 차단점일 때만 사용자에게 요청한다.
- 게시·결제·광고비는 명시된 승인 게이트를 통과해야 한다.

## 결과 보고 계약

각 최종 결과에 다음을 포함한다.

- 판정: `GOOD`, `BAD`, 또는 `REVIEW`
- 근거: 실제 관찰값과 검사 결과
- 출처: URL 또는 로컬 파일 링크
- 추론: 제공자와 모델
- 결과물: 게시 URL, 파일, 워크플로 ID, 커밋 등
- 다음 행동: 자동 진행 여부 또는 필요한 승인 1개

같은 내용은 중복 발송하지 않는다. 결과가 실질적으로 달라진 경우에만 Telegram으로 보낸다.

## 토큰 절약

- `rg`, SQL 집계, 상태 스크립트로 먼저 사실을 좁힌다.
- 대용량 JSON은 전체 출력하지 말고 필요한 노드·필드만 추출한다.
- 이미 검증된 기준을 다시 설명하거나 재조사하지 않는다.
- 로컬 모델이 처리 가능한 요약·후보 생성·형식 검사는 로컬 큐로 보낸다.
- Codex는 설계, 위험 판단, 코드 수정, 최종 검증에 집중한다.

## 기록 갱신

- 실제 상태가 달라지면 같은 변경에서 `docs/OPEN_ITEMS.md` 또는 기준 문서를 갱신한다.
- 새 자동화는 실행 주기, 소유자, 성공 조건, 실패 처리, 알림, 중복 방지를 기록한다.
- 생성된 상태 JSON과 런타임 결과물은 Git에 커밋하지 않는다.
- 관련 변경을 테스트하고, 정확한 커밋만 푸시한다.

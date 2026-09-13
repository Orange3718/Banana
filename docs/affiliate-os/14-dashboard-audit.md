# 14. 운영 대시보드 점검

점검일: 2026-09-13 KST · 상태: **REVIEW**

## 확인한 화면과 API

- 로컬 대시보드: `http://127.0.0.1:8765/atemoya-dashboard.html`
- 상태 API: `http://127.0.0.1:8765/api/status`
- 브라우저에서 실제 화면이 갱신되고, 메모리·Ollama·n8n·예약 작업·최근 결과·수집 근거·오류 목록이 표시되는 것을 확인했다.
- 현재 API 관찰: PostgreSQL/n8n 정상, Ollama `qwen3.5:4b` 설치·현재 추론 없음, 최근 30개 기록 중 실행 중 0개, 예약 작업 6개 등록.
- 예약 작업은 등록되어 있으나 화면의 `idle/예약됨`은 현재 실행 중이 아니라는 뜻이다. `runs` 횟수와 최근 로그 시각을 함께 봐야 한다.

## 발견된 문제

| 항목 | 실제 관찰 | 판정 | 의미 |
|---|---|---|---|
| 제휴 유입·수익 표 | `revenue_ops: []`, 화면은 “아직 연결된 유입·클릭·수익 기록이 없습니다.” | REVIEW | 0원이 아니라 이 대시보드에 공급자/GA 행이 연결되지 않은 상태. 수신 실패와 무성과를 구분해야 한다. |
| Autopilot 단계 | `queued 23`, `rejected 93`, `published 1`, `awaiting_approval 1` | REVIEW | 오래된 승인 기반 큐가 남아 있다. 사용자에게 현재 제휴 직접 게시 승인을 다시 요구할 근거가 아니다. 큐 정리·범위 표기가 필요하다. |
| 최근 오류 | Ollama fallback `SyntaxError` 반복, Telegram/제휴 페이지 점검 DNS 오류 | BAD | 대시보드는 오류를 보여주지만 자동 복구하지 않는다. 최근 실패가 해소됐다고 말할 수 없다. |
| 최근 수익 reconciler 로그 | `status=bad`, `수익 파이프라인이 72시간 이상 결과 없이 정체됨`, `published_7d=0`, `views_7d=0`, `affiliate_clicks_7d=0`, `revenue_7d=0` | BAD | 데이터 부재와 실제 0을 구분하지 않는 레거시 로그. 현재 affiliate 측정 계약과 불일치한다. |
| 공개 경계 | 공개 사이트에서 dashboard 문서와 내부 API 경로 HTTP 404 확인 | GOOD | 운영 상태와 수집 근거는 공개 산출물에 노출되지 않는다. |

## 이번 반영

상태 API에 `affiliate_measurement`를 추가했다.

- `state=no_provider_rows`: 공급자/GA 행이 없음.
- `interpretation=UNKNOWN—not zero...`: 데이터 없음과 0 성과를 분리한다.
- 행이 생겨도 source와 기간이 없으면 성과로 확정하지 않는다.

화면의 기존 수익 표 문구와 `awaiting_approval` 레거시 단계 자체는 아직 변경하지 않았다. 이 상태를 숨기기보다 다음 대시보드 UI 개편 작업으로 명시한다. 운영 대시보드가 상태 API의 새 필드를 표시하도록 바꾸기 전까지 API와 화면이 완전히 일치한다고 보고하지 않는다.

## 다음 작업

1. dashboard UI에 `affiliate_measurement.state`와 해석 문구를 표시한다.
2. Autopilot을 `legacy approval queue`와 `direct affiliate publication`으로 분리해 사용자 지시와 충돌하는 승인 대기 숫자를 분리한다.
3. reconciler가 데이터가 없을 때 `BAD/0` 대신 `WAIT_FOR_DATA`를 기록하는지 확인한다.
4. 반복 오류(SyntaxError, DNS)는 원인 수정 후 최근 실행 성공을 재검증한다. 대시보드가 오류를 보여주는 것만으로 복구된 것으로 보지 않는다.

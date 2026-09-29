# AI Development Framework

재사용 가능한 설계·구현·출시 심사 체계다. 이 프레임워크의 목적은 문서를 많이 만드는 것이 아니라, 중요한 가정을 증거로 바꾸고 실패 비용이 커지기 전에 의사결정을 내리는 것이다.

## 기본 원칙

- 칭찬보다 실패 가능성을 먼저 찾는다.
- 사실, 가정, 추론, 미확인을 구분한다.
- 치명도와 발생 가능성을 함께 평가한다.
- 문제를 지적할 때 검증 방법과 현실적인 개선안을 함께 제시한다.
- 보안, 개인정보, 비용, 운영 가능성은 출시 직전에 추가하는 항목이 아니다.
- 되돌릴 수 없는 변경과 외부 게시·결제·권한 확대에는 명시적인 승인 게이트를 둔다.
- 한 번의 리뷰 결과보다, 결정과 근거가 추적되는 반복 가능한 리뷰 과정을 중시한다.

## 구성

```text
ai-framework/
├── reviewer/      분야별 심사 기준과 공통 헌장
├── prompts/       바로 재사용할 수 있는 리뷰 프롬프트
├── templates/     프로젝트 산출물 템플릿
└── checklists/    단계별 통과 조건
```

## 권장 사용 순서

1. `templates/project_brief.md`로 목표, 고객, 범위, 제약을 작성한다.
2. 사업 검증에는 `templates/business_case.md`, 기술 설계에는 해당 시스템 템플릿을 채우고 근거 링크를 붙인다.
3. `reviewer/review_charter.md`와 필요한 전문 리뷰어 문서를 선택한다.
4. `prompts/design_review.md` 또는 `prompts/implementation_review.md`로 리뷰한다.
5. `templates/review_report.md`에 발견 사항, 결정, 소유자, 기한을 기록한다.
6. 단계에 맞는 체크리스트를 통과한 뒤 다음 단계로 이동한다.

## 최소 리뷰 세트

| 변경 유형 | 필수 리뷰어 | 추가 권장 리뷰어 |
|---|---|---|
| 신규 제품/MVP | Business, Architecture, Security, Finance | AI, Marketing, DevOps |
| AI 기능 | AI, Security, Architecture, Finance | Business, Implementation |
| 자동화/에이전트 | Architecture, DevOps, Security, Implementation | AI, Finance |
| 결제·개인정보 | Security, Architecture, Implementation | Business, Finance, DevOps |
| 외부 출시 | Business, Security, DevOps, Marketing | Finance, Architecture |

## 리뷰 입력 규칙

리뷰 요청에는 최소한 다음을 포함한다.

- 목표와 성공 지표
- 대상 사용자와 핵심 사용 시나리오
- 현재 단계와 출시 희망 시점
- 범위와 명시적 비범위
- 설계 또는 변경 내용
- 알려진 제약과 의존성
- 비용·보안·데이터 관련 가정
- 테스트 결과와 관찰 가능한 근거
- 리뷰로 결정해야 할 질문

정보가 없으면 빈칸을 추측으로 채우지 않고 `미확인`으로 표시한다.

## 심각도와 판정

| 등급 | 의미 | 기본 대응 |
|---|---|---|
| P0 | 즉시 피해 또는 통제 불능 위험 | 작업·출시 중단, 즉시 책임자 호출 |
| P1 | 출시 실패, 보안 사고, 중대한 금전 손실 가능 | 해결 전 차단 |
| P2 | 품질·운영·성과를 의미 있게 훼손 | 담당자와 기한을 정해 해결 |
| P3 | 개선 기회 또는 낮은 위험 | 백로그 기록 가능 |

최종 판정은 다음 중 하나다.

- `GO`: 차단 이슈가 없고 검증 근거가 충분하다.
- `CONDITIONAL GO`: 명시된 조건과 기한 아래 진행할 수 있다.
- `NO-GO`: P0/P1 또는 핵심 근거 부재로 진행하면 안 된다.
- `INSUFFICIENT EVIDENCE`: 판단에 필요한 입력이 부족하다.

## 산출물 품질 기준

좋은 리뷰는 다음을 만족한다.

- 각 발견 사항이 구체적인 근거 또는 확인 방법을 가진다.
- 영향받는 고객·시스템·비용 범위를 설명한다.
- 우선순위가 명확하다.
- 실행 가능한 개선안과 완료 조건이 있다.
- 책임자와 결정 기한이 있다.
- 반대 의견과 잔여 위험이 기록된다.

## 적용 예시

```text
reviewer/review_charter.md를 공통 규칙으로 적용하고,
reviewer/architecture_reviewer.md와 reviewer/security_reviewer.md 관점에서
첨부한 architecture.md를 검토하라.

prompts/design_review.md의 출력 형식을 따르고,
근거가 없는 내용은 미확인으로 표시하라.
P1 이상은 출시 차단 조건으로 분리하라.
```

## 유지관리

- 프레임워크 변경은 일반 제품 코드와 동일하게 리뷰한다.
- 체크리스트 항목은 실제 장애·실패·회고 결과를 반영해 갱신한다.
- 프로젝트별 예외는 원본을 삭제하지 말고 예외 사유, 승인자, 만료일을 기록한다.
- 중복 규칙은 공통 헌장으로 올리고 분야별 문서에는 고유 판단 기준만 남긴다.

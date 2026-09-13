# 09. 쿠팡파트너스 공급자 온보딩 계획

v1.0 · DECISION · 첫 공급자 선택 완료, 계정 증거 대기

## 결정

- 첫 공급자는 `Coupang Partners`로 고정한다.
- 사용자 상시 지시에 따라 별도 게시 승인 요청은 만들지 않는다. 대신 기술 QA·artifact hash·고지·링크·중복 검사를 통과한 콘텐츠만 직접 게시한다.
- 쿠팡 Open API(판매자용)와 쿠팡파트너스 성과/정산 기능은 서로 다른 제품일 수 있으므로 API 문서로 파트너스 실적 API를 추정하지 않는다.

## 공개 자료에서 확인한 사실

- [쿠팡파트너스 공식 사이트](https://partners.coupang.com/)는 가입, 광고 생성, 성과 리포트, 정산 시스템을 제공한다고 설명한다.
- [쿠팡 Open API 공식 가이드](https://developers.coupangcorp.com/hc/ko/categories/360001756693-Guides)는 판매자 Open API 문서다. 파트너스 계정의 실적 열·추적키·정산 주기를 보장하는 자료로 사용하지 않는다.

## 계정에서 확인할 증거

| 항목 | 필요한 증거 | 상태 |
|---|---|---|
| account_approved | 현재 포털 로그인 세션과 메뉴 접근 확인. 최종 승인 상태는 API 화면에서 별도 확인 필요 | OBSERVED/REVIEW |
| domain_approved | 게시 도메인 등록/승인 상태 | PENDING |
| link_generation | 저장소에 기존 생성 링크가 존재하며 공개 health workflow가 형식·고지를 검사 | OBSERVED(재검증 대기) |
| report_download | 익명화한 겹치는 기간의 성과 보고서 2개 | PENDING |
| stable_key | 링크/추적키 또는 주문·상품 식별자의 기간 간 안정성 | PENDING |
| commission_state | 예상·확정·취소·공제의 상태 정의 | PENDING |
| payout | 지급 ID·지급일·공제·실입금 관계 | PENDING |
| disclosure | 쿠팡 파트너스 활동 고지 문구·위치·정책 | PENDING |
| partners_api | 파트너스 API 안내 화면 확인. API 키 생성 버튼은 비활성화, 최종 승인 회원만 발급 가능 | REVIEW |

## 2026-09-13 포털 관찰

- 수익 요약 화면에서 9월·8월 수익금, 구매 금액, 취소 금액, 최종 수익금이 모두 `₩0`으로 표시됐다.
- 화면의 최근 업데이트는 `2026. 09. 13.`이다.
- 8월 최종 정산금액은 `9월 25일` 확정 예정이며 주문 취소 등에 따라 변경될 수 있다고 표시된다.
- 이는 계정이 연결되지 않았다는 뜻이 아니라, 현재 기간에 기록된 전환·확정 수익이 없다는 뜻으로 해석한다.

## 첫 수익 자산 게시

- 선택 상품: `LG전자 프라엘 더마 LED 마스크, BWJ1, 스틸 핑크`
- 쿠팡 상품 ID: `68486824`; item ID: `228589064`
- 생성 링크: `https://link.coupang.com/a/g0MPccSO4q`
- 적용 페이지: [LED 마스크 체크리스트](https://orange3718.github.io/Banana/offers/led-mask-checklist.html), [매일 사용 질문](https://orange3718.github.io/Banana/offers/led-mask-daily-use.html)
- 두 공개 URL 모두 HTTP 200과 쿠팡 고지 문구를 확인했다. 링크가 실제 주문·수익을 보장한다는 뜻은 아니다.

## 제출 형식

1. 구매자 이름·주소·전화·주문 상세 개인정보를 제거한다.
2. 원본 파일은 로컬 private 경로에 두고 Git에는 해시·필드 매핑·샘플 행만 남긴다.
3. 보고서마다 기간, 캡처 시각, 통화, 화면/파일 근거를 함께 기록한다.
4. 실제 키·토큰·쿠키는 문서·Git·Telegram에 기록하지 않는다.

## 다음 자동 진행 조건

- 증거가 도착하면 `policy_versions`에 쿠팡 계약 버전을 등록한다.
- 익명화 샘플 2개로 parser mapping·control total·중복·취소를 검증한다.
- 통과 후에만 `environment=prod`, `state=ready` 계정과 첫 실험 링크를 생성한다.

기존 작업에서 쿠팡파트너스 로그인 세션과 추적 링크가 이미 사용된 기록이 있고, 현재 포털에서도 로그인·메뉴 접근을 확인했다. 따라서 새 계정 연결은 필요하지 않다. 다만 API 키 발급은 최종 승인 조건 때문에 현재 자동화에 사용할 수 없다. 리포트는 포털에서 수동 다운로드하거나, 승인 후 API 키가 발급될 때만 API 연동을 검토한다.

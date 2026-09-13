# 09. 쿠팡파트너스 공급자 온보딩 계획

v1.0 · DECISION · 첫 공급자 선택 완료, 계정 증거 대기

## 결정

- 첫 공급자는 `Coupang Partners`로 고정한다.
- 운영 계정·승인·정산 조건을 확인하기 전에는 `prod/ready` 계정을 만들거나 실제 링크·수익을 원장에 기록하지 않는다.
- 쿠팡 Open API(판매자용)와 쿠팡파트너스 성과/정산 기능은 서로 다른 제품일 수 있으므로 API 문서로 파트너스 실적 API를 추정하지 않는다.

## 공개 자료에서 확인한 사실

- [쿠팡파트너스 공식 사이트](https://partners.coupang.com/)는 가입, 광고 생성, 성과 리포트, 정산 시스템을 제공한다고 설명한다.
- [쿠팡 Open API 공식 가이드](https://developers.coupangcorp.com/hc/ko/categories/360001756693-Guides)는 판매자 Open API 문서다. 파트너스 계정의 실적 열·추적키·정산 주기를 보장하는 자료로 사용하지 않는다.

## 계정에서 확인할 증거

| 항목 | 필요한 증거 | 상태 |
|---|---|---|
| account_approved | 과거 로그인 세션 기록은 있으나 현재 승인 상태 화면은 재검증하지 않음 | REVIEW |
| domain_approved | 게시 도메인 등록/승인 상태 | PENDING |
| link_generation | 저장소에 기존 생성 링크가 존재하며 공개 health workflow가 형식·고지를 검사 | OBSERVED(재검증 대기) |
| report_download | 익명화한 겹치는 기간의 성과 보고서 2개 | PENDING |
| stable_key | 링크/추적키 또는 주문·상품 식별자의 기간 간 안정성 | PENDING |
| commission_state | 예상·확정·취소·공제의 상태 정의 | PENDING |
| payout | 지급 ID·지급일·공제·실입금 관계 | PENDING |
| disclosure | 쿠팡 파트너스 활동 고지 문구·위치·정책 | PENDING |

## 제출 형식

1. 구매자 이름·주소·전화·주문 상세 개인정보를 제거한다.
2. 원본 파일은 로컬 private 경로에 두고 Git에는 해시·필드 매핑·샘플 행만 남긴다.
3. 보고서마다 기간, 캡처 시각, 통화, 화면/파일 근거를 함께 기록한다.
4. 실제 키·토큰·쿠키는 문서·Git·Telegram에 기록하지 않는다.

## 다음 자동 진행 조건

- 증거가 도착하면 `policy_versions`에 쿠팡 계약 버전을 등록한다.
- 익명화 샘플 2개로 parser mapping·control total·중복·취소를 검증한다.
- 통과 후에만 `environment=prod`, `state=ready` 계정과 첫 실험 링크를 생성한다.

기존 작업에서 쿠팡파트너스 로그인 세션과 추적 링크가 이미 사용된 기록이 있다. 따라서 새 계정 연결은 기본적으로 필요하지 않다. 다만 현재 브라우저 세션의 유효성, 계정 승인 상태, 성과 리포트 다운로드 권한은 별도 재검증 대상이다.

# 10. 조회수·클릭·수익 측정 맵

v1.0 · IMPLEMENTED · 직접 게시·쿠팡 수익화 경로

## 전체 흐름

```text
사용자 검색/공유
  → GitHub Pages 공개 HTML
  → CTA anchor (data-affiliate)
  → GA4 content_view / affiliate_click
  → 쿠팡 link.coupang.com
  → 쿠팡파트너스 리포트 (클릭·구매·수익·취소)
  → affiliate 원장 (확정 자료 수입 시)
```

## 어디에서 링크를 만들었는가

- 쿠팡파트너스 포털의 `링크 생성 → 상품 링크`에서 생성했다.
- 상품: LG전자 프라엘 더마 LED 마스크, BWJ1, 스틸 핑크
- 링크: `https://link.coupang.com/a/g0MPccSO4q`
- 링크 생성은 상품 선택과 추적 URL 발급이며, 주문·수익을 보장하지 않는다.

## 사용자가 어디를 클릭하는가

- [LED 마스크 체크리스트](https://orange3718.github.io/Banana/offers/led-mask-checklist.html)의 `쿠팡에서 상품 확인 →`
- [매일 사용 질문](https://orange3718.github.io/Banana/offers/led-mask-daily-use.html)의 `현재 상품 확인 →`
- 두 anchor 모두 `data-affiliate`, `rel="sponsored nofollow"`를 가진다.
- JavaScript가 꺼져도 anchor의 쿠팡 URL은 작동한다.

## 조회수와 클릭을 어디서 보는가

| 지표 | 시스템 | 확인 위치 | 의미 |
|---|---|---|---|
| 페이지 조회 | GA4 | 속성 `G-LKX74KWHLM`의 `content_view` | 페이지가 로드된 횟수. 중복·봇을 별도 판단 |
| 제휴 클릭 | GA4 | `affiliate_click`, `content_path`, `affiliate_host` | 버튼 클릭 관측값. 쿠팡 주문과 동일하지 않음 |
| 쿠팡 클릭/구매/수익 | 쿠팡파트너스 | 포털 `리포트 → 수익 요약` 및 다운로드 작업 | 공급자 성과·정산의 재무 근거 |
| 확정 원장 | PostgreSQL | `affiliate.v_program_balances`, `affiliate.v_content_economics` | 검증된 공급자 보고를 멱등 반영한 내부 잔액 |

현재 GA4 ID는 페이지에 설정되어 있으나 Data API 자동 조회 권한은 별도 연결 전이다. 따라서 GA4 콘솔의 실시간/보고서 값과 쿠팡 리포트는 각각 직접 제공하는 지표를 기준으로 보며, 둘을 자동으로 합산하지 않는다.

## 왜 이 플랫폼을 선택했는가

- GitHub Pages: 기존 사이트·도메인·CI 배포가 이미 있고 정적 콘텐츠와 직접 제휴 링크를 빠르게 운영할 수 있어 첫 비용을 0으로 유지했다.
- GA4: 공개 페이지 조회와 버튼 클릭을 콘텐츠 경로별로 관찰할 수 있고 기존 측정 ID가 있다.
- 쿠팡파트너스: 국내 상품 링크 생성과 공급자 성과·정산 리포트를 제공한다.
- PostgreSQL: 쿠팡 확정 자료를 pending/confirmed/cash로 분리하고 중복 없는 원장으로 보존한다.

GitHub Pages는 첫 실험의 source/deploy 경로로 사용했으며, 상업 규모 확대 시 이용 조건과 호스팅 이전을 재검토한다. 플랫폼 선택은 “무료라 무제한”이라는 뜻이 아니다.

## 맥락 없이 보였던 결정과 수정

- 이전에는 링크만 먼저 교체해 클릭·조회·쿠팡 수익의 각 소유 시스템을 한 문서에서 설명하지 못했다.
- 반복 원인: 기존 정적 페이지, GA4 설정, 쿠팡 포털, 신규 affiliate schema가 서로 다른 변경 단위였다.
- 이번 수정: GA4 `gtag('event')` 전송을 추가하고, 이 맵과 쿠팡 링크·공개 URL을 함께 기록했다.

## 현재 판정

- 공개 페이지와 링크: `GOOD`
- GA4 자동 리포트 회수: `REVIEW` (Data API 권한 미연결)
- 쿠팡 수익: `REVIEW` (현재 포털 0원)
- 확정 원장: `GOOD` (구조·멱등 fixture 검증), 실제 쿠팡 자료 수입은 대기

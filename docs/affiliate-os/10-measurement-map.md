# 10. 조회수·클릭·수익 측정 맵

v2.0 · 2026-09-13 · **계측 코드 배포 확인 / GA 수신·정산 자동 수입 미검증**

후속 원본 확보: 쿠팡 일별 보고서를 다운로드해 검사했다. 헤더만 있는 파일로, 확정 수익·현금 값으로 자동 전기하지 않았다([13번 기록](13-coupang-report-inspection.md)).

## 링크와 사용자 동선

```text
검색·공유 등 유입(현재 성과 미확인)
  → 공개 콘텐츠
  → “쿠팡에서 상품 확인” / “현재 상품 확인” 버튼
  → 쿠팡파트너스가 발급한 직접 제휴 URL
  → 쿠팡 구매 및 공급자 리포트
  → 검증된 원본 수입 후 내부 원장(아직 미연결)
```

- 링크 생성 장소: 쿠팡파트너스 포털 `링크 생성 → 상품 링크`.
- 상품: LG전자 프라엘 더마 LED 마스크 BWJ1, 스틸 핑크.
- 목적지: [쿠팡 제휴 링크](https://link.coupang.com/a/g0MPccSO4q).
- [LED 마스크 체크리스트](https://orange3718.github.io/Banana/offers/led-mask-checklist.html): `쿠팡에서 상품 확인 →`.
- [매일 사용 질문](https://orange3718.github.io/Banana/offers/led-mask-daily-use.html): `현재 상품 확인 →`.
- JS 없이도 실제 링크는 이동한다. 쿠팡 제휴 클릭은 직접 확인용으로 누르지 않았으며 테스트로 주문·클릭을 만들지 않았다.
- 두 페이지의 링크와 수수료 고지, HTTP 200을 2026-09-13 배포 후 확인했다.

## 어디에서 무엇을 보는가

| 지표 | 확인 위치 | 의미와 현재 한계 |
|---|---|---|
| 표준 조회수 | [Google Analytics](https://analytics.google.com/) → 보고서 → 참여도 → 페이지 및 화면, 경로별 Views | page_view 기반 표준 지표. content_view 맞춤 이벤트와 더하지 않는다. 실제 보고서 수신은 아직 미검증 |
| 콘텐츠 로드 진단 | GA4 content_view 이벤트 | 별도 맞춤 이벤트, 표준 Views나 순방문자와 동일하지 않음 |
| 제휴 버튼 클릭 | GA4 affiliate_click, content_path, link_key, measurement_version=v2 | data-affiliate로 표시된 HTTPS link.coupang.com/coupa.ng만 집계. 수신 검증 전에는 ‘전송 코드 구현’ 상태 |
| 내부 계산기 이동 | GA4 internal_cta_click | 내부 CTA. 제휴 클릭·구매로 계산하지 않음 |
| 일반 외부 이동 | GA4 outbound_click | 지정 쿠팡 제휴 링크와 구별. 외부 URL 쿼리를 맞춤 매개변수로 보내지 않음 |
| 쿠팡 클릭·구매·수수료 | [수익 요약](https://partners.coupang.com/#affiliate/ws/report/earning), [다운로드 작업](https://partners.coupang.com/#affiliate/ws/report/download-tasks) | 공급자 측 원본. GA 클릭과 일치한다고 가정하지 않음. 0원 관찰은 기간과 보고서 완전성을 붙여야 함 |
| 확정 수익·현금 | PostgreSQL affiliate 원장 | 구조와 단일 사례 smoke는 있으나 실제 보고서 parser/import 및 전체 조회 정합성 검증은 미완료 |

메뉴 구성은 속성에 따라 다를 수 있다. [Google 공식 페이지 및 화면 보고서 안내](https://support.google.com/analytics/answer/12926732).

`G-LKX74KWHLM`은 **측정 ID**이지 숫자형 GA4 속성 ID가 아니다. 기존 로그인으로 Atemoya Analytics 화면까지 접근했지만 이메일 수신 설정 창 때문에 상세 보고서를 확인하지 못했다. 숫자형 속성과 이 측정 ID의 매핑·수신, Data API 접근은 UNKNOWN이다. ‘새 계정이 필요’ 또는 ‘API 권한이 없다’로 단정하지 않는다.

## 계측 검증의 단계

1. 로컬: 8개 오프라인 이벤트 검사 PASS. 실제 GA 요청과 제휴 클릭을 발생시키지 않음.
2. 배포: main 19ed415, Actions 34754415577 성공. 공개 analytics.js 본문이 로컬 수정본과 일치.
3. 수신: 미검증. 브라우저에 코드가 존재해도 네트워크 차단·설정·동의 상태에 따라 이벤트가 수신되지 않을 수 있다.
4. 보고·운영: 자동 보고서 회수와 원장 결합은 미완료. 현재 값을 알 수 없으면 UNKNOWN이지 0이 아니다.

맞춤 이벤트 전송과 수신 확인은 [Google 공식 GA4 이벤트 문서](https://developers.google.com/analytics/devguides/collection/ga4/events)를 기준으로 한다. 수정 전 data-affiliate 내부 버튼이 affiliate_click으로 계산될 수 있었으므로 v1/v2를 같은 정의로 전후 비교하지 않는다.

## 플랫폼 선택 이유와 정정

- 기존 정적 사이트·Git 배포가 있었기 때문에 GitHub Pages를 재사용했다. 초기 구현 비용을 낮추려는 운영 판단이었지만, 사업용 호스팅의 현재 적합성을 먼저 검증하지 않은 것은 누락이다.
- [GitHub 공식 제한](https://docs.github.com/en/pages/getting-started-with-github-pages/github-pages-limits)은 상업 거래 촉진이 주목적인 사업의 무료 호스팅 사용을 허용하지 않는다고 설명한다. 제휴 수익을 주목적으로 하는 현재 설계는 적합성 위험이 있으므로 ‘커지면 이전’이 아니라 지금 해결할 문제로 기록한다.
- 기존 사이트의 오류·공개 노출은 수정하되, 적합한 운영 경로 확인 전 대량 게시와 유료 유입 확대는 진행하지 않는다. 새 계정·비용을 임의로 만들지 않고 기존 연결부터 조사한다.
- GA4는 기존 설정을 활용하는 조회/이벤트 관측 수단이지 수익 원장이나 주문 증명이 아니다.
- 쿠팡파트너스는 사용자가 선택한 첫 제휴 공급자다. 공급자 리포트가 수수료 근거이며 아직 수익 성과를 입증한 것은 아니다.
- PostgreSQL은 원본·수정 이력·정산/입금을 분리할 기반이지만 전체 정합성이 검증되기 전 확정 운영 원장으로 보고하지 않는다.

## 현재 판정

공개 파일 수정은 검증 완료. **전체는 REVIEW**: 호스팅 적합성·GA 수신·공급자 수입·실제 전환·자동 게시/수집은 미완료다. 다음 행동과 차단 사유는 [11. 실행 상태](11-execution-status.md)에 이어서 기록한다.

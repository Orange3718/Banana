# SNS 성공 사례 비교

기준일: 2026-08-22

## 확인한 실제 신호

- TikTok #ledmask: 130개 영상, 총 1,320만 조회, 평균 10.1만 조회
- 상위 사례: 13초 270만 조회, 55초 210만 조회, 4분 27초 290만 조회
- TikTok #tiktokshopmademebuyit: 평균 54.2만 조회, 최근 성장률 +1,732%
- #redlightherapy는 평균 2,800회로 훨씬 낮아, 해시태그만 붙인다고 유입되지 않음

## 고조회수 구조

1. 첫 1~2초에 실제 제품·착용 장면 또는 강한 질문
2. 제품 설명보다 가격 차이·실패·댓글 질문을 먼저 제시
3. 7~15초의 짧은 버전과 30~60초의 설명 버전을 함께 운영
4. 화면에 사람이 등장하거나 제품이 실제로 움직임
5. 마지막에만 구매 링크나 체크리스트 CTA

## Atemoya 현재 영상 평가

현재 v2는 글자 가독성은 좋지만 정적 카드형이고 제품·사람·소리가 없어 고조회수 사례와 다르다. 따라서 ‘게시 완료’가 아니라 ‘실험용 기준선’으로 취급한다.

## 다음 실험

- A: 가격 충격 훅 — “23,900원과 329,320원, 차이는 어디서 생길까?”
- B: 댓글 답변 훅 — “LED 마스크 매일 써도 되나요?”
- C: 실패 방지 훅 — “광원 수만 보고 샀다가 놓치는 3가지”

각 7~15초 버전을 로컬 모델 대본으로 만들고, 같은 페이지로 연결하되 GA4에서 영상별 유입과 affiliate_click을 분리한다. 인위적인 조회·클릭은 만들지 않는다.

### 출처

- [#ledmask TikTok 분석](https://toklytics.app/hashtag/ledmask)
- [#tiktokshopmademebuyit TikTok 분석](https://toklytics.app/hashtag/tiktokshopmademebuyit)
- [#redlightherapy TikTok 분석](https://toklytics.app/hashtag/redlightherapy)

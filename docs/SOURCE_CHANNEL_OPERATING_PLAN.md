# Atemoya 채널별 수집 운영계획

## 즉시 운영 중

- GitHub Search API: 새 저장소·스타 증가
- Hacker News Algolia: 인기 기술 글
- Google News RSS: 국내·해외 상품·기술 뉴스
- 커머스 트렌드 HTTP 수집: 공개 행사·상품 신호

## 다음 확장 순서

1. YouTube Data API 또는 공개 검색 결과 — 조회수·게시일·댓글·제목
2. Reddit 공개 JSON/API — 해외 구매 불만·비교 질문
3. 네이버 검색/블로그 공개 결과 — 국내 검색어·제목·상위 글 형식
4. 네이버 카페 — 공개 검색 결과만, 로그인·비공개 게시물 제외
5. TikTok/Instagram — 공식 Creative Center와 공개 해시태그 지표만
6. Pinterest·Product Hunt·Indie Hackers — 해외 제품·아이디어 신호

각 채널은 `source_channel`, `source_url`, `published_at`, `engagement`, `collected_at`을 공통 형식으로 정규화한다. 로컬 모델은 수집된 자료만 분석하고 결과에 다음 주석을 붙인다.

`[출처: 채널/URL] [수집시각: KST] [추론: 모델명]`

## 운영 안전선

- 공식 API·RSS·공개 검색 결과만 사용
- 로그인 우회, 비공개 카페, 대량 자동 댓글·좋아요·팔로우 금지
- API 키·쿠키·개인 토큰은 Git과 문서에 저장하지 않음
- 채널별 오류는 해당 채널만 건너뛰고 나머지 수집은 계속
- 수익성 판단은 조회수만 보지 않고 구매 의도·제휴 가능성·운영 부담을 함께 평가

현재 n8n은 위의 즉시 운영 4개를 사용 중이며, 다음 작업은 YouTube·Reddit·네이버 공개 검색을 같은 정규화 스키마로 추가하는 것이다.

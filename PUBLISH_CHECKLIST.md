# Atemoya 게시 전 계정 연결표

코드는 게시 준비가 끝났다. 아래 값은 공개 식별자이며 GitHub 저장소의 `Settings → Secrets and variables → Actions → Variables`에 넣는다. 비밀번호·2FA·계좌·주민번호는 넣지 않는다.

| Variable 이름 | 어디서 확인 | 언제 입력 |
|---|---|---|
| `ATEMOYA_CONTACT_EMAIL` | 사업용 Gmail 주소 | 게시 전 필수 |
| `ATEMOYA_AFFILIATE_URL` | 쿠팡파트너스에서 만든 가습기 비교/검색 링크 | 파트너스 승인 후 |
| `ATEMOYA_GA_ID` | Google Analytics 웹 스트림의 `G-...` | 분석 연결 시 |
| `ATEMOYA_ADSENSE_CLIENT` | AdSense의 `ca-pub-...` | 사이트 승인 후 |
| `ATEMOYA_GOOGLE_VERIFY` | Search Console HTML 태그의 content 값 | DNS 인증을 안 쓸 때 |
| `ATEMOYA_NAVER_VERIFY` | Naver Search Advisor HTML 태그의 content 값 | 사이트 등록 시 |

쿠팡파트너스에서는 카테고리별 링크를 만든 뒤 아래 변수에 넣는다. 하나의 공통 링크보다 글의 문제와 정확히 맞는 검색결과·제품군 링크를 사용한다.

`AFFILIATE_HUMIDIFIER`, `AFFILIATE_HEATING`, `AFFILIATE_PURIFIER`, `AFFILIATE_DISPOSER`, `AFFILIATE_ROBOT`, `AFFILIATE_BEAUTY`, `AFFILIATE_FEEDER`, `AFFILIATE_LLM`, `AFFILIATE_TRAVEL`, `AFFILIATE_BLACKFRIDAY`

연결 전에는 글의 버튼이 무료 계산기로 이동한다. 연결 후에는 경제적 이해관계 고지가 나타나고 해당 카테고리의 쿠팡파트너스 링크로 이동한다.

외부 채널은 추가로 다음 연결만 한다.

| 채널 | Owner가 연결할 것 | 자동화 수준 |
|---|---|---|
| Blogger | Google OAuth 승인, Blog ID 선택 | 공식 API로 초안 자동 생성 가능 |
| Tistory | 카카오 계정으로 블로그 개설 | 공식 쓰기 API 종료로 HTML 초안까지만 자동 |
| Naver Blog | 네이버 블로그 개설 | 플랫폼 맞춤 초안까지만 자동 |
| YouTube | 사업용 Google 계정 채널·고급 기능 | 스크립트·설명·썸네일 초안, 공개 승인 필요 |

## 게시 순서

1. 사업용 이메일 변수만 먼저 입력한다.
2. `Actions → Deploy static site to Pages → Run workflow`를 누른다.
3. 공개 주소에서 계산기와 문의 이메일을 확인한다.
4. Search Console과 Naver Search Advisor에 사이트를 등록하고 sitemap.xml을 제출한다.
5. 쿠팡파트너스 승인 후 제휴 URL 변수를 넣고 workflow를 다시 실행한다.
6. 원본 콘텐츠가 충분히 쌓이고 AdSense 승인을 받은 뒤 AdSense 변수를 넣는다.
7. Blogger OAuth를 n8n에 연결하면 외부 글은 항상 `초안` 상태로 생성한다.
8. Tistory와 Naver는 생성된 HTML/문안을 붙여 넣고 미리보기 후 공개한다.

계정 값이 비어 있으면 해당 기능만 숨겨지며 계산기와 정보 글은 정상 작동한다.

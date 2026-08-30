# Atemoya 운영 계약

## 사용자에게 반복해서 묻지 않을 것

- 이미 승인된 프로젝트 방향, 로컬 우선 정책, GitHub 푸시 의사
- 안전한 읽기·검사·초안·내부 기록·비파괴적 마이그레이션
- 공개 API/RSS 수집과 로컬 분석
- 오류 복구, 중복 방지, 상태 정리, 테스트

## 사용자 입력이 필요한 경우

- 비밀번호, OTP, 2FA, CAPTCHA, 복구코드
- 결제수단, 비용 지출, 광고비
- 법적 약관 동의
- 실제 외부 게시의 GOOD/BAD 승인(해당 워크플로에서 요구할 때)

## 현재 상시 작업

- `com.atemoya.local-llm`: 매시간 로컬 작업 2개
- `com.atemoya.source-scout`: 매시간 HN·Reddit·Google News 수집 및 로컬 분석
- `com.atemoya.nightly-reflection`: 매일 03:00 KST 반추
- `com.atemoya.local-llm-status`: 상태 화면 서버 유지
- n8n: PostgreSQL·Telegram·커머스·트렌드 워크플로

상시 작업이 정말 실행 중인지 `launchctl` 상태뿐 아니라 최근 로그·DB 시각으로 검증한다.

## 게시 운영

- 초안은 근거 링크, 제휴 링크, 대가성 고지를 포함한다.
- Telegram에서 `GOOD / BAD / 수정: ...`으로 승인받는다.
- GOOD일 때만 외부 게시하고 URL을 저장한다.
- 게시 후 GA4·제휴 클릭·구매 신호를 측정한다.

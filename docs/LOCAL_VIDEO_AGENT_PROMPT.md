# Atemoya 로컬 영상 제작 에이전트

이 프로젝트의 재사용 프롬프트는 Codex skill `atemoya-video-agent`에 등록되어 있다.

핵심 실행 순서:

`주제·리뷰 분석 → 30초 기획 → 8컷 스토리보드 → 실제 Source Photos 확보 → 부족한 장면만 생성 → assets 저장 → 1440×2560 MP4 렌더 → Neural TTS → 실제 재생 QA → SEO 메타데이터·랜딩페이지 → Google Drive 업로드 → 링크·로컬 경로 보고`

필수 규칙:

- 업로드된 실제 사진을 먼저 사용하고 원본은 변경하지 않는다.
- placeholder·가짜 이미지·근거 없는 장면으로 렌더링하지 않는다.
- 원본은 `inputs/assets/<project_slug>/source-01.jpg`, 생성 이미지는 `scene-01.png`에 저장한다.
- 25–35초, 9:16, 1440×2560, 30fps, H.264/AAC를 검증한다.
- `ko-KR-SunHiNeural`을 우선 사용하며 빠른 음성·SAPI·`atempo` 보정을 금지한다.
- 최종 영상·음성·스토리보드·메타데이터·SEO 랜딩·Drive manifest를 모두 남긴다.
- 실제 Drive URL과 로컬 절대경로를 확인하기 전에는 `GOOD` 또는 게시 완료라고 말하지 않는다.

상세 계약은 `/Users/orange/.codex/skills/atemoya-video-agent/references/video-production-contract.md`에 있다.

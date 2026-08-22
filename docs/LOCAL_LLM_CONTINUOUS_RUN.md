# 로컬 LLM 지속 운영

`com.atemoya.local-llm` LaunchAgent가 로그인 후 즉시 한 번 실행하고, 이후 6시간마다 실행한다. 두 레인은 한 번의 실행 안에서 병렬 처리하며, 잠금 디렉터리로 중복 실행을 막는다.

- 실행 로그: `/tmp/atemoya-local-llm-supervisor.log`
- 상태 화면: `http://127.0.0.1:8765/local-llm-status.html`
- 중지: `launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.atemoya.local-llm.plist`
- 재시작: `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.atemoya.local-llm.plist`

이 주기는 현금흐름 작업을 방해하지 않도록 6시간으로 설정했다. SNS 조사·제목 실험 결과는 PostgreSQL에 남고, 실제 게시·결제·계정 변경은 자동 실행하지 않는다.

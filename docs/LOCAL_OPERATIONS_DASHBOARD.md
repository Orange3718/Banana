# 로컬 운영 대시보드

## 사용

- iMac: `http://127.0.0.1:8765/atemoya-dashboard.html`
- 같은 Wi‑Fi: `http://192.168.200.198:8765/atemoya-dashboard.html`
- Tailscale 연결: `http://100.102.120.59:8765/atemoya-dashboard.html`

5초마다 `/api/status`를 다시 읽는다. 기존 `local-llm-status.html` 주소도 유지된다.

## 지표 정의와 원천

- 메모리: macOS `vm_stat`의 전체 메모리에서 free/inactive/speculative 페이지를 제외한 관찰값. 성능 모니터링용이며 메모리 압력 지표와 동일하지 않다.
- 예약 작업: `~/Library/LaunchAgents` plist와 `launchctl print`의 등록·실행 횟수. 실행 사이 `idle`은 예약이 해제됐다는 뜻이 아니다.
- 현재/최근 작업: PostgreSQL `local_llm_runs` 최근 30건. 모델·제공자·상태·결과·소요시간을 그대로 표시한다.
- 수집 근거: PostgreSQL `source_observations` 최근 12건의 채널·제목·원문 URL.
- 서비스: n8n `/healthz`, Ollama `/api/tags`와 `/api/ps`.

운영판은 사실을 생성하지 않으며, 외부 게시·결제·계정 인증 상태를 대신하지 않는다.

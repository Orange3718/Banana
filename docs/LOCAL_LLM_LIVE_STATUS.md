# 로컬 LLM 실시간 작업판

실행:

```bash
python3 tools/local-llm-runner.py
python3 -m http.server 8765 --directory tools
```

브라우저에서 [http://127.0.0.1:8765/local-llm-status.html](http://127.0.0.1:8765/local-llm-status.html)을 열면 3초마다 Postgres의 작업상태를 읽는다.

현재는 `qwen3.5:4b` 하나를 공유하되, `research`와 `content` 두 레인을 병렬로 큐에 넣는다. 16GB M1에서 동시에 모델 5개를 메모리에 올리지 않는다. 모델별 결과·소요시간·오류는 `local_llm_runs`에 남는다.

## GitHub 유사 구조 조사

- Ollama 본체는 `OLLAMA_NUM_PARALLEL`로 모델별 동시 처리 수를 제어하고 기본값은 1이다. [Ollama FAQ](https://github.com/ollama/ollama/blob/main/docs/faq.mdx)
- `ollama-queue-proxy`는 우선순위 큐와 `/queue/status`·Prometheus 지표를 제공한다. [GitHub](https://github.com/TadMSTR/ollama-queue-proxy)
- `ollama-agent-router`는 작업종류·큐 깊이·자원에 따라 모델을 선택한다. [GitHub](https://github.com/ExeconOne/ollama-agent-router)

Atemoya는 외부 프로젝트를 중복 설치하지 않고, 기존 n8n/Postgres 오케스트레이터 안에 작업기록과 가벼운 상태판을 먼저 넣었다. 큐가 커질 때만 별도 proxy/router를 검토한다.

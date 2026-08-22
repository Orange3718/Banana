# 무료 외부 API 후보

2026-08-22 공식 문서 기준으로 확인한 결과다. 무료라고 표시된 서비스도 한도 초과 시 과금될 수 있으므로 결제수단을 연결하지 않는 원칙으로 운용한다.

| 제공자 | 무료 범위 | Atemoya 용도 | 판단 |
|---|---|---|---|
| GroqCloud | Free Plan rate limit 제공 | 빠른 짧은 요약·분류 | 무료 키를 직접 발급받은 뒤에만 선택 |
| OpenRouter | 무료 모델만 선택 시 50 requests/day | 장애 시 대체 요약 | 반드시 `openrouter/free` 또는 `:free` 모델만 사용 |
| Hugging Face Inference Providers | Free 계정 월 $0.10 크레딧 | 아주 작은 실험 | 운영 주력으로는 부족 |
| DeepSeek API | 공식 API는 토큰 과금 | 사용하지 않음 | 무료 API로 간주 금지 |
| DeepSeek 로컬 모델 | Ollama/자체 실행이면 API 비용 없음 | 긴 초안·비교 | 현재 Qwen 로컬 우선, M1 16GB에서 별도 모델 동시 실행 금지 |

우선순위는 `Ollama → Groq 무료 티어(키가 있을 때) → OpenRouter 무료 모델(하루 50회 이내) → Gemini 무료 범위`다. 결제·자동충전·유료 fallback은 설정하지 않는다.

근거: [Groq 무료 플랜 한도](https://console.groq.com/docs/rate-limits), [OpenRouter 무료 요금제](https://openrouter.ai/pricing), [OpenRouter 무료 라우터](https://openrouter.ai/models?pricing=free), [Hugging Face 무료 크레딧](https://huggingface.co/docs/inference-providers/main/en/pricing), [DeepSeek 공식 가격](https://api-docs.deepseek.com/quick_start/pricing?push_animated=1&show_loading=0&theme=light)

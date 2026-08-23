# 로컬 이미지·영상 준비

## 현재 Mac 기준

- Apple M1, 16GB 통합 메모리
- 이미지 런타임: `coremltools`, `diffusers`, `imageio-ffmpeg` 설치
- 썸네일 후보: Apple `coreml-stable-diffusion-v1-5`
- 영상: FFmpeg 기반 이미지→세로 MP4 합성부터 사용

SDXL·Flux·대형 영상 확산 모델은 16GB 환경에서 n8n/Ollama와 병렬 실행할 때 메모리 압박이 커서 보류한다. 생성형 영상 모델은 별도 메모리 여유가 확인된 뒤 평가한다.

모델 다운로드는 `com.atemoya.media-model-prepare`가 재시도 가능한 방식으로 수행한다. 상태는 `~/AtemoyaModels/media-model-status.json`에 기록하며, 가중치 자체는 Git에 넣지 않는다.

# 결과 보고·피드백·이미지 모델 기준

## Telegram 최종 보고 형식

모든 최종 결과는 다음 순서를 지킨다.

1. 결론: `GOOD` / `BAD` / `REVIEW`
2. 근거: 원문 제목·수치·게시일 등 실제 관찰값
3. 링크: 출처 URL을 최소 1개 이상
4. 추론: 제공자와 모델명
5. 결과물: 초안·이미지 경로·다음 행동
6. 사용자 피드백: `GOOD`, `BAD`, `수정: ...` 중 하나를 요청

출처가 없거나 결과물이 비어 있으면 GOOD을 보내지 않고 `REVIEW`로 보낸다.

## 로컬 이미지 모델 후보

- 1순위: Draw Things + FLUX.1-schnell MLX. Apple Silicon에서 Metal/MLX로 실행하는 빠른 초안·썸네일 후보다. FLUX.1-schnell 원본은 Apache-2.0 모델 카드가 있다.
- 2순위: Apple Core ML SDXL base. Apple Silicon macOS GPU용 Core ML 가중치가 있어 상업용 썸네일 실험에 적합하다.
- 보류: FLUX.2 klein 9B. Apple Silicon MLX 경로는 있으나 비상업 라이선스라 Atemoya 수익 자산에는 사용하지 않는다.

현재 iMac은 M1·16GB이므로 이미지 모델을 여러 개 동시에 올리지 않는다. 먼저 1개 모델로 1024px 썸네일 1장을 생성하고 시간·메모리·품질을 기록한 뒤 채택한다. 이미지는 로컬에서 생성하고, 결과 보고에는 파일 경로와 생성 모델을 기록한다.

참고: [FLUX.1-schnell 모델 카드](https://huggingface.co/black-forest-labs/FLUX.1-schnell), [Apple Core ML SDXL](https://huggingface.co/apple/coreml-stable-diffusion-xl-base), [Draw Things 모델 지원](https://engineering.drawthings.ai/p/bf16-and-image-generation-models-803cf0515bee), [FLUX.2 klein 비상업 라이선스](https://huggingface.co/SceneWorks/flux2-klein-9b-mlx)

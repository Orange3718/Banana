# Neural Trade 세션 인수인계

저장 시점: 2026-09-07 KST

## 사용자 목표

Windows에서 개발을 계속하고 최종 운영 환경은 Mac 또는 고정 IP 서버로 이전한다. Upbit 현물, Binance USD-M 선물, 국내주식은 인증·주문·장애 영역을 각각 분리하고 대시보드, 원장, 전략 연구, 알림만 공통으로 사용한다.

## 변경하면 안 되는 원칙

- 실제 `.env`와 API 키를 문서, 로그, Git, ZIP에 넣지 않는다.
- 출금 권한을 사용하지 않는다.
- 신규 Neural API에는 주문 실행기를 연결하지 않는다.
- Upbit, Binance, 국내주식 주문 워커를 각각 독립시킨다.
- Windows, Mac, 서버에서 같은 주문 워커를 동시에 실행하지 않는다.
- KRW와 USD 자산을 환율 근거 없이 합산하지 않는다.
- 설정 초안은 사용자가 활성화하기 전까지 기존 워커에 적용하지 않는다.

## 현재 구축 상태

| 영역 | 상태 |
| --- | --- |
| React 사이버펑크 대시보드 | 구축·빌드 완료 |
| FastAPI 조회 API | 실행 중 |
| SQLite 원장 | 정상 |
| Upbit 전체 보유자산 조회기 | 구축 완료, 현재 허용 IP 불일치 401 |
| Binance USD-M 조회기 | 구축 완료, 인증 전 disabled |
| 국내주식 | 설계만 완료 |
| 전략 연구실 | Donchian, Dual Thrust, RSI2·볼린저 구현 |
| 백테스트 | 합성 캔들 기능 검증, 비용·낙폭·손익비 계산 |
| 신규 주문 API | 미구현, POST 명령은 409로 차단 |
| Telegram 신규 설정 적용 | 초안 저장만 가능, 실제 발송기 연결 전 |
| Mac 이전 | 설치·시작·중지·복원·사전점검 스크립트 완료 |

## 마지막 검증 결과

- Python 테스트: 15 passed
- TypeScript/Vite production build: 통과
- Upbit 공개 API: 200
- Binance Futures 공개 ping/time: 200
- 대시보드 전략 연구실: 브라우저 표시 확인
- 주문 명령 엔드포인트: 409 차단 확인
- 기존 거래 워커: 최신 heartbeat 없음, 실행 확인 안 됨

## 현재 로컬 주소

```text
http://127.0.0.1:8765
```

## 원격지에서 재개하는 순서

1. 최신 `upbit-auto-trader-mac-*.zip`을 개인 장비로 안전하게 옮긴다.
2. 압축을 풀고 프로젝트 폴더에서 설치 스크립트를 실행한다.
3. `migration/neural-export.json`을 빈 원장에 복원한다.
4. `python -m neural.preflight`로 공개 API와 환경을 확인한다.
5. `SESSION_HANDOFF.md`와 `USER_GUIDE_KO.md`를 먼저 읽는다.
6. 인증 전에는 `.env`를 만들더라도 실거래를 활성화하지 않는다.
7. 개발을 마치면 다시 세션 저장 스크립트를 실행한다.

Mac 명령:

```bash
bash tools/setup_macos.sh
.venv-next/bin/python -m neural.manage restore --file migration/neural-export.json
.venv-next/bin/python -m neural.preflight
bash tools/start_neural.sh
```

Windows 명령:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\resume_session.ps1
```

## 다음 개발 우선순위

1. CSV·JSON 과거 캔들 가져오기와 데이터 품질 검사
2. 학습·검증·최종시험 기간 분리 백테스트
3. 전략별 자산곡선·낙폭·월별 성과 그래프
4. Telegram 알림 우선순위·중복 제거·발송 주기 실제 적용
5. 모의 포트폴리오와 실계좌 결과 대조
6. 집에서 Mac 공인 IP 등록과 조회 전용 인증
7. 장기간 조회·모의검증 후 주문 워커 별도 설계 검토

## 주요 문서

- `USER_GUIDE_KO.md`: 사용자 조작법과 용어
- `MAC_MIGRATION.md`: Mac 이전 절차
- `MASTER_BUILD_AND_MIGRATION_PLAN.md`: 장기 구축 계획
- `MULTI_ASSET_STOCK_DESIGN.md`: 멀티자산 상세설계
- `SESSION_HANDOFF.md`: 현재 세션 재개 기준점

## 주요 코드

- `neural/api.py`: 조회 API와 주문 차단
- `neural/store.py`: 거래소별 원장
- `neural/collector.py`: Upbit 조회
- `neural/binance_futures.py`: Binance 선물 조회
- `neural/strategy_lab.py`: 오프라인 전략·백테스트
- `neural/preflight.py`: 인증 없는 사전점검
- `apps/dashboard/src/main.tsx`: 대시보드 UI

## 인증 관련 미완료 작업

집에서 실제 실행 장비의 공인 IP를 확인해 Upbit와 Binance 각각의 API 허용 IP에 등록해야 한다. 현재 확인했던 Windows 공인 IP는 이동 후 재사용하지 말고 Mac에서 다시 확인한다. 키 값은 대화에 입력하지 않는다.

# 원격 작업 런북

이 문서는 다른 컴퓨터나 맥에서 `upbit-auto-trader` 작업을 이어가기 위한 운영 문서입니다.

## 1. GitHub 위치

- 저장소: <https://github.com/Orange3718/Banana>
- 작업 브랜치: `feat/upbit-auto-trader`
- 작업 폴더: `upbit-auto-trader/`
- 브랜치 바로가기: <https://github.com/Orange3718/Banana/tree/feat/upbit-auto-trader/upbit-auto-trader>
- PR 생성 화면: <https://github.com/Orange3718/Banana/pull/new/feat/upbit-auto-trader>

현재 `Banana/main`은 기존 프로젝트이므로, 자동매매 프로젝트는 작업 브랜치 안의 `upbit-auto-trader` 폴더에서 관리합니다. 기존 `main`에 병합하기 전까지는 기존 프로젝트에 영향을 주지 않습니다.

## 2. 다른 컴퓨터에서 최초 준비

```bash
git clone -b feat/upbit-auto-trader https://github.com/Orange3718/Banana.git
cd Banana/upbit-auto-trader
chmod +x tools/*.sh
./tools/setup_macos.sh
```

Windows에서는 해당 폴더를 열고 `start_neural_dashboard.bat`를 실행할 수 있습니다.

## 3. 환경변수 준비

`.env`는 비밀정보 보호를 위해 Git에 저장하지 않습니다.

```bash
cp .env.example .env
```

`.env`에 Upbit 키, Telegram 토큰/Chat ID, Binance Futures 키/Secret, Binance 사용 여부를 직접 입력합니다. 인증키가 없어도 공개 시세, 화면, 오프라인 전략 검증은 실행할 수 있습니다.

## 4. 실행과 확인

```bash
./tools/start_neural.sh
```

브라우저: `http://127.0.0.1:8765`

종료:

```bash
./tools/stop_neural.sh
```

확인 순서:

1. 통합 운영 탭에서 서비스 상태와 마지막 갱신 시각을 확인합니다.
2. Upbit 현물 탭에서 보유자산과 KRW 환산 금액을 확인합니다.
3. Binance Futures 탭에서 `disabled` 또는 연결 상태를 확인합니다.
4. 전략 실험실에서 과거 데이터 기반 결과를 검증합니다.
5. 이벤트 탭에서 API 오류, 인증 오류, 데이터 지연을 확인합니다.

## 5. 원격지에서 작업 이어가기

작업 시작 전:

```bash
git switch feat/upbit-auto-trader
git pull origin feat/upbit-auto-trader
```

수정 후:

```bash
git add .
git commit -m "변경 내용을 짧게 작성"
git push origin feat/upbit-auto-trader
```

작업을 중단할 때는 커밋하고 push합니다. 다른 컴퓨터에서는 다시 `git pull`하면 이어서 작업할 수 있습니다.

## 6. 검증 명령

```bash
python -m pytest -q
```

```bash
cd apps/dashboard
npm run build
```

```bash
curl http://127.0.0.1:8765/api/v1/health
```

## 7. 현재 구현 범위

- Upbit 현물과 Binance Futures의 계정 분리
- 읽기 전용 계좌/시세 수집
- 전체 보유자산의 KRW 환산 표시
- 실시간 상태, 이벤트, 거래/로그 현황 화면
- Donchian, Dual Thrust, RSI2/Bollinger 오프라인 전략 실험실
- 수수료, 슬리피지, 손절, 익절, 승률, 순수익, 최대낙폭 계산
- 전략/파라미터 설명, 초보자용 도움말
- 맥 실행 스크립트와 세션 인계 문서
- 주문 API 미연결 상태의 안전한 실행 경계

## 8. 다음 작업 체크리스트

- [ ] 맥에서 clone 및 대시보드 실행 확인
- [ ] Upbit API 허용 IP를 실제 실행 환경 IP로 등록
- [ ] Upbit 읽기 전용 잔고/주문조회 연결 검증
- [ ] Binance Futures 읽기 전용 키와 IP 제한 설정
- [ ] 텔레그램 알림 주기, 우선순위, 중복 억제 검증
- [ ] 보유자산별 거래 이력과 실현/미실현 손익 대조
- [ ] 전략 백테스트 결과와 실제 로그의 공통 포맷 확정
- [ ] 모의주문 또는 paper trading 검증
- [ ] 주문 executor, 위험 한도, kill switch를 별도 승인 후 구현
- [ ] 운영 서버 배포, 비밀정보 저장소, 모니터링/백업 구성

## 9. 장애 대응

- `http_401` 또는 `no_authorization_ip`: 거래소 등록 허용 IP와 현재 실행 IP가 다른지 확인합니다.
- `request failed after retries`: 이벤트 탭에서 원인과 마지막 성공 시각을 확인하고 반복 호출을 중지한 뒤 API 제한과 네트워크를 점검합니다.
- 자산 금액 불일치: 거래소 응답 시각, KRW 환산 기준가, 잔고 수량, 수수료를 순서대로 대조합니다.
- Telegram 폭주: 알림 설정에서 이벤트 종류와 주기를 줄이고 동일 이벤트 억제를 확인합니다.
- 데이터 정지: API health, 프로세스 heartbeat, 로그의 마지막 기록 시각을 함께 확인합니다.

## 10. 보안 규칙

- `.env`, 토큰, API secret, 개인키는 commit하지 않습니다.
- 거래소 키는 출금 권한을 끄고 IP 제한을 사용합니다.
- 원격 작업자는 읽기 전용부터 검증합니다.
- 실제 주문은 별도 executor와 위험 한도 검증 후에만 다룹니다.
- 로그에 키, Authorization 헤더, 전체 계좌 식별자를 남기지 않습니다.


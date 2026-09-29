# Mac 이전 및 실행 안내

현재 구축 범위는 Upbit와 Binance USD-M 선물의 계좌 조회입니다. 신규 대시보드에는 주문 API가 연결되어 있지 않습니다. 인증 전에는 Binance 수집기가 `disabled` 또는 `missing_credentials` 상태로 대기합니다.

## 1. Windows에서 가져갈 파일

가장 간단한 방법은 Windows에서 다음 스크립트를 실행해 생성된 ZIP을 Mac으로 옮기는 것입니다.

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File tools\build_mac_bundle.ps1
```

ZIP에는 `.env`, API 키, Telegram 데스크톱 데이터, 가상환경과 로그가 포함되지 않습니다. `migration/neural-export.json`에는 계좌 조회 이력이 들어 있으므로 ZIP 자체는 개인 금융자료로 취급합니다.

프로젝트 폴더 전체를 외장 디스크나 암호화된 개인 저장소로 복사하되 다음 폴더는 제외해도 됩니다.

- `.venv`, `.venv-next`, `node_modules`, `apps/dashboard/dist`
- `logs`, `next_data/run`, `next_data/logs`
- `tools/telegram-portable`

과거 조회 기록을 유지하려면 `next_data/neural.db`를 포함합니다. `.env`에는 인증키가 있으므로 일반 메신저나 공개 저장소로 전송하지 않습니다. 가장 안전한 방법은 Mac에서 `.env.example`을 복사한 뒤 키를 직접 다시 입력하는 것입니다.

## 2. Mac 준비

Homebrew가 설치된 Mac 터미널에서 실행합니다.

```bash
brew install python@3.11 node@22
cd "/path/to/upbit-auto-trader"
bash tools/setup_macos.sh
```

기존 이력을 복원하려면 서비스를 시작하기 전에 실행합니다.

```bash
.venv-next/bin/python -m neural.manage restore --file migration/neural-export.json
```

Apple Silicon과 Intel Mac 모두 Python 가상환경 안에서 설치됩니다. 기존 `.env`가 있으면 설치 스크립트는 덮어쓰지 않습니다.

## 3. 실행과 중지

```bash
bash tools/start_neural.sh
bash tools/stop_neural.sh
```

대시보드 주소는 `http://127.0.0.1:8765`입니다. Finder에서 실행하려면 최초 한 번 아래 권한을 적용한 뒤 `.command` 파일을 더블클릭합니다.

```bash
chmod +x start_neural_macos.command stop_neural_macos.command tools/*.sh
```

인증 없이 환경과 공개 API 연결을 확인할 수 있습니다.

```bash
.venv-next/bin/python -m neural.preflight
```

## 4. 인증은 집에서 진행

현재 IP 문제를 해결하기 전에는 `.env`에서 다음 값을 유지합니다.

```env
BINANCE_FUTURES_ENABLED=false
DRY_RUN=true
ENABLE_REAL_TRADE=false
```

집에서 실행할 Mac의 공인 IP를 Upbit와 Binance 각각의 API 허용 IP에 등록합니다. Mac과 Windows가 같은 집 공유기에 연결되어 있으면 대개 공인 IP가 같지만, 반드시 Mac에서 다시 확인합니다.

```bash
curl https://api.ipify.org && echo
```

키를 설정한 뒤에는 Binance 조회만 다음과 같이 활성화합니다.

```env
BINANCE_FUTURES_ENABLED=true
BINANCE_API_KEY=직접_입력
BINANCE_SECRET_KEY=직접_입력
```

Binance 키에는 필요한 계좌 조회 권한만 먼저 부여하고 출금 권한은 부여하지 않습니다. 선물 주문 권한은 조회 검증과 모의 운영이 끝난 뒤 별도 단계에서 추가합니다.

## 5. 이전 검증 순서

1. Windows의 모든 거래 워커를 중지합니다.
2. `next_data/neural.db`와 필요한 JSON 설정을 Mac으로 복사합니다.
3. Mac 시간을 자동 동기화합니다. Binance 서명 요청은 시각 차이에 민감합니다.
4. Mac에서 대시보드와 수집기만 시작합니다.
5. Upbit와 Binance 상태가 `connected`인지 확인합니다.
6. 두 거래소의 잔고와 대시보드 값을 직접 대조합니다.
7. Windows와 Mac에서 동시에 주문 워커를 실행하지 않습니다.

로그는 `next_data/logs`에, PID 파일은 `next_data/run`에 저장됩니다.

## 6. 다른 장소에서 개발 재개

`SESSION_HANDOFF.md`가 현재 개발 상태와 다음 우선순위의 기준 문서입니다. 설치와 복원이 끝난 뒤 다음 명령으로 사전점검과 대시보드 시작을 한 번에 수행합니다.

```bash
bash tools/resume_session.sh
```

Codex 대화 세션과 프로젝트 파일은 별개입니다. 같은 계정으로 대화를 열더라도 최신 이동 ZIP을 원격 장비에 먼저 복원해야 동일한 코드 상태에서 이어갈 수 있습니다.

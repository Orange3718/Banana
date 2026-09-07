# Upbit Auto Trader

Upbit Open API 기반 로컬 자동매매/모니터링 도구입니다. 기본값은 `DRY_RUN=true`, `ENABLE_REAL_TRADE=false`라 실제 주문을 보내지 않습니다.

## 실행 방식

PowerShell 명령을 직접 입력하지 않고 아래 파일을 더블클릭해서 실행합니다.

- `start_dashboard.bat`: 브라우저 대시보드만 실행
- `start_trading_worker.bat`: 자동매매 워커 실행, 기본은 일시정지 상태
- `start_telegram_control.bat`: 텔레그램 모바일 제어 봇 실행
- `start_all.bat`: 대시보드, 워커, 텔레그램 제어를 함께 실행

대시보드 주소:

```text
http://127.0.0.1:8501
```

## 상태 모니터링

대시보드 상단의 `Status Monitoring / Remote Control` 영역에서 다음 상태를 확인하고 제어할 수 있습니다.

- 실행 상태: `PAUSED`, `RUNNING`, `KILL SWITCH`
- 마지막 가격, 전략 신호, heartbeat
- `Start / Resume`, `Pause`, `Kill Switch`, `Reset Kill`

자동매매 워커는 시작 직후 항상 일시정지 상태입니다. 실제 루프를 돌리려면 대시보드에서 `Start / Resume`을 눌러야 합니다.

## 텔레그램 모바일 제어

1. 모바일 텔레그램에서 `@BotFather`를 검색합니다.
2. `/newbot`으로 봇을 만들고 토큰을 받습니다.
3. `.env`에 토큰을 입력합니다.

```env
TELEGRAM_BOT_TOKEN=123456789:your_bot_token
TELEGRAM_ALLOWED_CHAT_ID=
```

4. `start_telegram_control.bat`를 실행합니다.
5. 모바일에서 만든 봇에게 `/start`를 보냅니다.
6. 봇이 알려주는 chat id를 `.env`에 넣습니다.

```env
TELEGRAM_ALLOWED_CHAT_ID=123456789
```

7. `start_telegram_control.bat`를 다시 실행합니다.

사용 가능한 명령:

```text
/status
/resume
/pause
/kill
/reset
/help
```

## 안전 설정

`.env`의 기본 안전 설정:

```env
DRY_RUN=true
ENABLE_REAL_TRADE=false
```

실제 주문은 두 값을 모두 아래처럼 바꿔야 가능하지만, 충분한 모의 검증 전에는 변경하지 마세요.

```env
DRY_RUN=false
ENABLE_REAL_TRADE=true
```

API Key, Secret Key, Telegram Token은 브라우저 화면이나 로그에 노출하지 않도록 관리합니다.
# 원격 작업 시작점

- [원격 작업 런북](REMOTE_RUNBOOK_KO.md)
- [설계 사상](DESIGN_PRINCIPLES_KO.md)
- [세션 인계 문서](SESSION_HANDOFF.md)
- [맥 이관 가이드](MAC_MIGRATION.md)
- [사용자 가이드](USER_GUIDE_KO.md)

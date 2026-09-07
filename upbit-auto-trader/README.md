# Upbit Auto Trader

Upbit Open API 기반 개인 자동매매/모니터링 도구입니다. 읽기 전용 대시보드와
실제 주문을 담당하는 레거시 워커는 별도 경로입니다. 현재 iMac에서는 운영 설정에
따라 Upbit 워커가 실제 주문을 수행할 수 있으므로 `.env`와 LaunchAgent 상태를
반드시 함께 확인합니다.

## 실행 방식

PowerShell 명령을 직접 입력하지 않고 아래 파일을 더블클릭해서 실행합니다.

- `start_dashboard.bat`: 브라우저 대시보드만 실행
- `start_trading_worker.bat`: 자동매매 워커 실행, 기본은 일시정지 상태
- `start_telegram_control.bat`: 텔레그램 모바일 제어 봇 실행
- `start_all.bat`: 대시보드, 워커, 텔레그램 제어를 함께 실행

맥 서버 대시보드 주소:

```text
http://127.0.0.1:8766
```

Windows/기존 Streamlit 대시보드 주소:

```text
http://127.0.0.1:8501
```

## 상태 모니터링

대시보드 상단의 `Status Monitoring / Remote Control` 영역에서 다음 상태를 확인하고 제어할 수 있습니다.

- 실행 상태: `PAUSED`, `RUNNING`, `KILL SWITCH`
- 마지막 가격, 전략 신호, heartbeat
- `Start / Resume`, `Pause`, `Kill Switch`, `Reset Kill`

현재 iMac의 `com.orange3718.upbit-auto-trader.upbit-worker`는 LaunchAgent로
자동 시작됩니다. 대시보드 API는 주문을 보내지 않으며, 실제 주문 경로는 워커의
설정·로그·거래소 체결 결과에서 확인합니다.

## 텔레그램 모바일 제어

`telegram_bot.py`는 개인 봇 제어 코드다. 회사 Atemoya n8n Telegram 봇과 같은
토큰을 사용해 웹훅과 `getUpdates` 폴링을 동시에 실행하면 수신 충돌이 발생할 수
있으므로 개인 전용 봇 토큰을 사용한다. 현재 iMac에는 이 제어 봇 LaunchAgent가
등록되어 있지 않다.

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

## iMac 서버 상태

현재 Atemoya iMac에서는 기존 운영 대시보드가 8765 포트를 사용하므로, 이 앱은 `NEURAL_PORT=8766`으로 실행합니다. API, Upbit 읽기 전용 수집기, Binance Futures 읽기 전용 수집기는 LaunchAgent로 등록해 로그인 시 자동 시작되도록 구성합니다.

현재 Binance는 읽기·모의운용 경로만 운영하며 실주문 실행기는 연결하지 않았다.
실제 Binance 주문 전에는 계약 단위, 레버리지, 보호주문, 펀딩비, 재시작 대사와
24시간 모의운용을 별도로 통과해야 한다.
# 원격 작업 시작점

- [원격 작업 런북](REMOTE_RUNBOOK_KO.md)
- [설계 사상](DESIGN_PRINCIPLES_KO.md)
- [세션 인계 문서](SESSION_HANDOFF.md)
- [맥 이관 가이드](MAC_MIGRATION.md)
- [사용자 가이드](USER_GUIDE_KO.md)

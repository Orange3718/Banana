# Atemoya Operations Guardian

## 역할

- macOS Watchdog: n8n 외부에서 15분마다 생존성과 신선도를 검사한다.
- n8n Guardian: 매일 03:10 KST 지난 24시간 운영·품질·현금흐름을 검토한다.
- PostgreSQL: 모든 검사, 사건 전환, 일일 보고의 기준 기록이다.
- Ollama: 규칙 판정 이후의 한국어 설명만 작성한다.

## 판정과 임계값

- 컨테이너·n8n·PostgreSQL·Ollama 불능: `BAD`
- 수집 3시간 초과, 로컬 완료 4시간 초과, 디스크 5GB 미만: `BAD`
- n8n 오류 1~2건/2시간, 수집 2~3시간, 메모리 여유 20% 미만: `REVIEW`
- n8n 오류 3건 이상/2시간, 메모리 여유 10% 미만: `BAD`
- 예약 작업의 `not running`은 오류가 아니다. 최근 결과 시각으로 판단한다.

## 자동복구 허용 목록

1. 멈춘 기존 컨테이너 `docker start`
2. HTTP 불능 n8n 컨테이너 1회 재시작
3. 오래된 소스 수집 LaunchAgent 재실행
4. 만료된 로컬 `running/queued` 기록을 오류로 정리

같은 복구는 한 시간에 한 번만 시도한다. 게시, 결제, DB 삭제, 볼륨 변경,
credential 변경, migration 적용은 Watchdog에서 금지한다.

## 알림 중복 방지

사건 지문은 `component + check_code`이다. 오류 문장이 달라져도 같은 사건은
다시 보내지 않는다. `open → resolved` 또는 `resolved → open`처럼 상태가
바뀔 때만 Telegram으로 보낸다. 일일 보고는 DB의 `notified_at`으로 날짜당
한 번만 보낸다.

## 수동 검증

```bash
PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 tools/ops-watchdog.py --dry-run
curl -X POST http://127.0.0.1:5678/webhook/atemoya-ops-guardian-run
```

첫 명령은 기록·복구·알림 없이 검사한다. 두 번째 명령은 일일 보고 흐름을
수동 실행하지만 이미 보고한 날짜에는 Telegram을 다시 보내지 않는다.

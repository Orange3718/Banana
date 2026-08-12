# 원격 접속·Docker·n8n 구축 기록

작성일: 2026-08-12  
목적: 다른 Windows 노트북과 휴대폰에서 원래 iMac의 자동화 환경을 안전하게 관리하기 위한 재개 기록

## 저장소

- GitHub: `Orange3718/Banana`
- Windows 로컬 경로: `C:\Users\yoo\Banana`
- 원격 주소: `git@github.com:Orange3718/Banana.git`
- 기본 브랜치: `main`

## 완료된 작업

### 1. Tailscale 원격망

- Windows 노트북과 원래 iMac을 동일한 Tailscale 계정으로 연결했다.
- Windows 장치: `LAPTOP-3DAN1CC2`
- iMac 장치: `Orange의 iMac`
- iMac Tailscale IP: `100.102.120.59`
- iMac MagicDNS: `orange-imac.tail14202a.ts.net`
- 같은 Tailscale 계정의 휴대폰에서도 iMac과 n8n에 접근할 수 있다.

### 2. iMac 원격 접속

- macOS 화면 공유를 켰다.
- Windows에 TightVNC Viewer를 설치했다.
- VNC 접속 주소: `100.102.120.59`
- 화면 크기는 TightVNC의 화면 맞춤 기능으로 조정했다.
- macOS 원격 로그인을 켰다.
- Mac 사용자 이름: `orange`
- SSH 접속 명령: `ssh orange@100.102.120.59`
- Windows 노트북의 SSH 공개키를 Mac에 등록해 비밀번호 없는 SSH 접속을 확인했다.

> VNC 전용 암호, Mac 로그인 암호, SSH 개인키는 이 문서에 기록하지 않는다.

### 3. Windows GitHub 환경

- Git 설치 확인: `git 2.53.0.windows.3`
- 이 노트북 전용 ED25519 SSH 키를 만들었다.
- GitHub 계정 `Orange3718`에 공개키를 등록했다.
- GitHub SSH 인증을 확인했다.
- `Orange3718/Banana` 저장소를 Windows에 복제하고 `pull`을 확인했다.

### 4. iMac Docker Desktop

- Apple Silicon용 Docker Desktop을 설치했다.
- Docker Desktop 버전: `4.86.0`
- Docker Engine 버전: `29.7.2`
- `hello-world` 테스트 컨테이너 실행에 성공했다.
- Docker Desktop은 Mac에서 계속 실행 상태를 유지해야 한다.

### 5. PostgreSQL과 n8n

- Docker 네트워크: `atemoya-net`
- PostgreSQL 컨테이너: `atemoya-postgres`
- n8n 컨테이너: `atemoya-n8n`
- PostgreSQL 이미지: `postgres:16-alpine`
- n8n 이미지 및 확인 버전: `n8nio/n8n:latest`, n8n `2.34.5`
- 영구 볼륨: `atemoya-postgres`, `atemoya-n8n`
- 두 컨테이너 모두 `unless-stopped` 자동 재시작 설정을 사용한다.
- PostgreSQL 포트는 외부에 공개하지 않았다.
- n8n 접속 포트는 `5678`이다.

휴대폰 또는 Tailscale 연결 기기에서 사용할 주소:

- `http://orange-imac.tail14202a.ts.net:5678`
- 대체 주소: `http://100.102.120.59:5678`

### 6. Telegram 연결

- Telegram BotFather로 봇을 생성했다.
- n8n에 `Telegram API` 자격 증명을 저장했다.
- Telegram 대화 ID를 확인했다.
- n8n의 `Telegram 연결 테스트` 워크플로로 휴대폰 메시지 전송에 성공했다.
- 반복 전송을 막기 위해 테스트 워크플로는 비활성화했다.

> Telegram Bot API 토큰과 n8n 관리자 암호는 이 문서에 기록하지 않는다.

## 평상시 사용 방법

### Windows에서 Mac 화면 열기

1. Windows와 Mac에서 Tailscale이 켜져 있는지 확인한다.
2. TightVNC Viewer를 실행한다.
3. `100.102.120.59`에 접속한다.
4. Mac에서 만든 VNC 전용 암호를 직접 입력한다.

### Windows에서 Mac 터미널 접속

```text
ssh orange@100.102.120.59
```

### 저장소 최신화

```text
cd C:\Users\yoo\Banana
git pull --ff-only
```

### 서버 상태 확인

Mac에 SSH 접속한 뒤 Docker Desktop이 실행 중인 상태에서 다음을 확인한다.

```text
docker ps
```

정상 상태라면 `atemoya-n8n`과 `atemoya-postgres`가 `Up`으로 표시된다.

## 다음에 이어서 할 작업

1. AI 비즈니스 트렌드 수집 대상과 주기를 결정한다.
2. 신뢰할 수 있는 뉴스·공식 블로그·기술 소스를 선정한다.
3. n8n에서 수집 → 중복 제거 → AI 요약 → 분류 흐름을 만든다.
4. 요약 결과를 Telegram으로 자동 전송한다.
5. 실패 알림, 재시도, 실행 기록 보존을 설정한다.
6. 필요하면 안정적인 HTTPS 웹훅 주소를 구성해 Telegram 수신 자동화도 연결한다.
7. 마지막 단계에서 Obsidian Vault 저장 흐름을 연결한다.

## 재개할 때 확인 순서

1. Mac 전원과 Tailscale 연결 확인
2. SSH 접속 확인
3. Docker Desktop 실행 확인
4. `atemoya-n8n`, `atemoya-postgres` 컨테이너 상태 확인
5. 휴대폰에서 n8n 주소 접속 확인
6. 이 문서의 `다음에 이어서 할 작업`부터 진행


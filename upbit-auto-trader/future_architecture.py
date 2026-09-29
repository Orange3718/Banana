from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SystemModuleSpec:
    name: str
    responsibility: str
    future_file: str
    dashboard_surface: str
    implementation_status: str = "설계 반영"


@dataclass(frozen=True)
class OperationModeSpec:
    level: int
    name: str
    decision_policy: str
    trade_policy: str
    telegram_policy: str
    recommended_use: str


@dataclass(frozen=True)
class TelegramCommandSpec:
    command: str
    purpose: str
    example: str
    decision_effect: str
    allowed_from_mode: str


@dataclass(frozen=True)
class DashboardTabSpec:
    tab_name: str
    purpose: str
    main_controls: tuple[str, ...]
    beginner_explanation: str


@dataclass(frozen=True)
class CoinGroupSpec:
    group_name: str
    default_policy: str
    examples: tuple[str, ...]
    description: str


SYSTEM_MODULES: tuple[SystemModuleSpec, ...] = (
    SystemModuleSpec(
        "운영 모드 정책",
        "1단계부터 4단계까지 추천, 승인, 자동매매 허용 범위를 결정합니다.",
        "operation_mode.py",
        "운영 / 모니터링 탭",
    ),
    SystemModuleSpec(
        "코인 등록부",
        "업비트 KRW 마켓 중 감시, 제외, 그룹, 그룹별 정책을 저장합니다.",
        "coin_registry.py",
        "코인 관리 탭",
    ),
    SystemModuleSpec(
        "마켓 스캐너",
        "거래대금, 거래량 증가율, 변동성, 유의 종목 여부로 후보 코인을 걸러냅니다.",
        "market_scanner.py",
        "추천 코인 탭",
    ),
    SystemModuleSpec(
        "추천 엔진",
        "후보 코인에 점수를 부여하고 TOP N 추천 목록과 추천 사유를 생성합니다.",
        "recommendation_engine.py",
        "추천 코인 탭",
    ),
    SystemModuleSpec(
        "텔레그램 의사결정",
        "추천 승인, 거절, 제외, 그룹 이동, 운영 단계 변경 명령을 처리합니다.",
        "telegram_decision.py",
        "Telegram 설정 / 로그 탭",
    ),
    SystemModuleSpec(
        "알림 설정",
        "어떤 항목을 어떤 주기로 Telegram에 보낼지 저장하고 필터링합니다.",
        "notification_settings.py",
        "알림 설정 탭",
    ),
    SystemModuleSpec(
        "백테스터",
        "과거 캔들로 승률, 수익률, 최대 낙폭, 거래 횟수를 계산합니다.",
        "backtester.py",
        "일일 복기 탭",
    ),
    SystemModuleSpec(
        "일일 복기",
        "매일 저녁 오늘의 매매와 더 좋았을 조건을 비교한 리포트를 만듭니다.",
        "daily_reviewer.py",
        "일일 복기 탭",
    ),
)


OPERATION_MODES: tuple[OperationModeSpec, ...] = (
    OperationModeSpec(
        1,
        "추천 전용",
        "시스템이 추천 코인을 보여주고 Telegram으로 물어봅니다.",
        "실제 주문은 하지 않습니다. 승인해도 기록 또는 모의 판단까지만 수행합니다.",
        "추천, 추천 사유, 승인/거절 예시 명령을 보냅니다.",
        "초기 검증, 전략 튜닝, 초보자 운영",
    ),
    OperationModeSpec(
        2,
        "승인형 실제 추천 매매",
        "시스템이 진입 후보를 찾으면 Telegram 승인을 요청합니다.",
        "사용자가 /approve 해야 설정된 금액과 그룹 정책 안에서 실제 매수합니다. 손절/익절은 사전 설정된 조건만 자동 실행합니다.",
        "추천 사유를 함께 보내고, /why로 추가 사유 조회, /approve 또는 /reject로 의사결정을 받습니다.",
        "모의매매 안정화 후 제한적 실거래 검토",
    ),
    OperationModeSpec(
        3,
        "그룹 제한 자동매매",
        "사용자가 허용한 코인 그룹 안에서만 자동 진입합니다.",
        "고위험 그룹은 승인형, 안전 그룹은 자동형처럼 그룹별 정책을 다르게 적용합니다.",
        "자동 진입 전후 결과를 보고하고 사용자의 중단/제외 명령을 받습니다.",
        "충분한 로그와 복기 결과가 쌓인 뒤",
    ),
    OperationModeSpec(
        4,
        "완전 자동 운영",
        "추천, 선정, 진입, 청산을 자동으로 수행합니다.",
        "킬 스위치, 일일 손실 제한, 최대 거래 횟수 제한이 반드시 켜져야 합니다.",
        "주기 리포트와 이상 상황 경보 위주로 운영합니다.",
        "장기간 모의/소액 실거래 검증 후",
    ),
)


TELEGRAM_COMMANDS: tuple[TelegramCommandSpec, ...] = (
    TelegramCommandSpec("/status", "현재 봇 상태 확인", "/status", "상태만 조회합니다.", "1단계 이상"),
    TelegramCommandSpec("/recommend", "추천 코인 TOP N 확인", "/recommend", "현재 추천 목록과 점수를 조회합니다.", "1단계 이상"),
    TelegramCommandSpec("/why", "추천 사유 확인", "/why KRW-ETH", "해당 코인의 추천 근거와 위험 요인을 조회합니다.", "1단계 이상"),
    TelegramCommandSpec("/approve", "추천 코인 승인", "/approve KRW-ETH", "설정된 금액, 그룹, 리스크 조건 안에서 실제 진입을 허용합니다.", "2단계 이상"),
    TelegramCommandSpec("/reject", "추천 코인 거절", "/reject KRW-ETH 과열이라 보류", "이번 추천 후보에서 제외하고 사용자의 거절 사유를 기록합니다.", "1단계 이상"),
    TelegramCommandSpec("/watch", "감시 목록 추가", "/watch KRW-SOL", "지정 코인을 감시 대상으로 추가합니다.", "1단계 이상"),
    TelegramCommandSpec("/exclude", "제외 목록 추가", "/exclude KRW-DOGE", "지정 코인을 추천/매매 후보에서 제외합니다.", "1단계 이상"),
    TelegramCommandSpec("/include", "제외 해제", "/include KRW-DOGE", "제외했던 코인을 다시 후보에 포함합니다.", "1단계 이상"),
    TelegramCommandSpec("/group", "코인 그룹 지정", "/group KRW-ETH major", "코인을 지정 그룹으로 이동합니다.", "1단계 이상"),
    TelegramCommandSpec("/mode", "운영 단계 변경", "/mode 2", "추천 전용, 승인형, 그룹 제한 자동매매 등으로 변경합니다.", "1단계 이상"),
    TelegramCommandSpec("/style", "거래 성향 변경", "/style aggressive", "보수적, 균형, 적극적 거래 성향으로 추천/진입 기준을 조정합니다.", "1단계 이상"),
    TelegramCommandSpec("/pause", "자동매매 일시정지", "/pause", "신규 판단과 주문 실행을 멈춥니다.", "1단계 이상"),
    TelegramCommandSpec("/kill", "긴급 차단", "/kill", "주문 판단을 강하게 차단합니다.", "1단계 이상"),
)


APPROVAL_FLOW: tuple[tuple[str, str], ...] = (
    ("1. 후보 탐색", "설정된 코인 그룹과 제외 목록을 기준으로 업비트 KRW 마켓을 스캔합니다."),
    ("2. 추천 점수 계산", "거래대금, 거래량 증가율, 추세, RSI, 변동성, 최근 백테스트 성과를 점수화합니다."),
    ("3. 승인 요청", "추천 코인, 예상 진입금액, 손절/익절 기준, 추천 사유, 위험 요인을 Telegram으로 보냅니다."),
    ("4. 사용자 질문", "사용자는 /why KRW-XXX로 더 자세한 추천 사유와 반대 근거를 물어볼 수 있습니다."),
    ("5. 사용자 결정", "/approve는 설정 범위 안에서만 진입을 허용하고, /reject는 거절 사유를 기록합니다."),
    ("6. 주문 전 최종 검증", "승인 후에도 잔고, 최소 주문, 일일 손실, 최대 포지션, 그룹 정책을 다시 확인합니다."),
    ("7. 실제 주문", "모든 검증을 통과할 때만 Upbit API로 시장가 주문을 보냅니다."),
    ("8. 결과 기록", "주문 결과, 추천 사유, 사용자 승인/거절 사유를 trade_history.jsonl에 남깁니다."),
)


DASHBOARD_TABS: tuple[DashboardTabSpec, ...] = (
    DashboardTabSpec(
        "실시간 현황",
        "현재 봇 상태, 포지션, 손익률, 추천 코인, 마지막 의사결정을 한눈에 봅니다.",
        ("자동 새로고침", "하트비트", "마지막 신호", "마지막 주문 결과", "추천 TOP 5"),
        "초보자는 이 탭에서 봇이 살아 있는지, 지금 주문할 가능성이 있는지 먼저 확인합니다.",
    ),
    DashboardTabSpec(
        "운영 / 모니터링",
        "운영 단계, 자동매매 허용 범위, 일일 손익, 승인 대기 건을 관리합니다.",
        ("운영 단계 선택", "Pause", "Kill Switch", "승인 대기 목록"),
        "1단계는 추천만, 2단계는 승인 후 매매, 3단계는 허용 그룹 자동매매입니다.",
    ),
    DashboardTabSpec(
        "코인 관리",
        "업비트 등록 코인을 감시, 제외, 그룹으로 나눕니다.",
        ("전체 KRW 마켓 조회", "감시 체크박스", "제외 체크박스", "그룹 선택"),
        "잘 모르는 코인은 제외하거나 추천만 받는 그룹에 두면 됩니다.",
    ),
    DashboardTabSpec(
        "추천 코인",
        "거래대금, 추세, RSI, 변동성, 최근 백테스트 점수로 추천 코인을 보여줍니다.",
        ("추천 갱신", "추천 사유", "위험 점수", "Telegram 승인 요청"),
        "추천 점수가 높아도 자동 매수하지 않고, 운영 단계에 따라 사용자에게 물어봅니다.",
    ),
    DashboardTabSpec(
        "파라미터 설정",
        "투자금, 손절, 익절, 추천 기준, 알림 주기를 설정합니다.",
        ("총 운용금액", "코인당 최대금액", "손절률", "익절률", "추천 갱신 주기"),
        "각 파라미터 옆에는 의미, 낮게/높게 설정했을 때의 효과, 초보자 권장값을 표시합니다.",
    ),
    DashboardTabSpec(
        "일일 복기",
        "매일 저녁 실제/모의 매매와 과거 데이터 백테스트를 비교합니다.",
        ("승률", "총 수익률", "최대 낙폭", "더 좋았을 파라미터", "내일 참고 조건"),
        "승률만 보지 않고 수익률, 손익비, 최대 손실을 함께 봅니다.",
    ),
)


COIN_GROUPS: tuple[CoinGroupSpec, ...] = (
    CoinGroupSpec(
        "대형 코인",
        "2단계 승인형 또는 3단계 제한 자동매매 후보",
        ("KRW-BTC", "KRW-ETH", "KRW-XRP", "KRW-SOL"),
        "거래대금이 크고 유동성이 높은 코인을 묶습니다.",
    ),
    CoinGroupSpec(
        "거래량 상위",
        "2단계 승인형 후보",
        ("KRW-ADA", "KRW-DOGE", "KRW-AVAX"),
        "최근 거래대금과 거래량 증가율이 높은 코인을 매일 갱신해 묶습니다.",
    ),
    CoinGroupSpec(
        "고위험 관찰",
        "추천만 표시하고 자동매매 금지",
        ("급등락 코인", "스프레드 큰 코인"),
        "변동성이 크거나 추격 매수 위험이 큰 코인을 둡니다.",
    ),
    CoinGroupSpec(
        "사용자 제외",
        "추천, 감시, 매매 모두 제외",
        ("직접 제외한 코인", "유의 종목", "거래량 부족 코인"),
        "사용자가 체크박스로 제외한 코인과 시스템 제외 코인을 모읍니다.",
    ),
)


PERSISTENCE_FILES: tuple[tuple[str, str], ...] = (
    ("coin_registry.json", "감시/제외/그룹 설정 저장"),
    ("notification_settings.json", "Telegram 알림 항목과 주기 저장"),
    ("recommendation_state.json", "현재 추천 목록, 점수, 사유 저장"),
    ("trade_history.jsonl", "모의/실거래 주문과 판단 이력 저장"),
    ("daily_reviews.json", "일일 복기 결과 저장"),
)

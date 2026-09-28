from __future__ import annotations

from dataclasses import asdict
from typing import Callable

from coin_registry import CoinEntry, load_registry, save_registry, set_coin_policy, sync_markets
from config import Config
from market_scanner import get_krw_markets, scan_candidates
from recommendation_engine import format_recommendation_message, generate_recommendations
from recommendation_state import (
    Recommendation,
    RecommendationState,
    append_history,
    find_recommendation,
    load_recommendation_state,
    save_recommendation_state,
)
from runtime_state import update_state
from settings_store import TRADING_STYLES, TradingSettings, load_settings, update_settings
from upbit_client import UpbitClient


SendFn = Callable[[int | str, str], None]


def _client(config: Config) -> UpbitClient:
    return UpbitClient(config.access_key, config.secret_key, config.base_url)


def _format_recommendation_list(state: RecommendationState, settings: TradingSettings) -> str:
    if not state.recommendations:
        return "현재 추천 코인이 없습니다. 대시보드에서 코인 관리/필터 설정을 확인해 주세요."
    lines = [
        f"추천 생성 시간: {state.generated_at}",
        f"운영 단계: {settings.mode_label}",
        f"시장 상태: {state.market_regime or '-'}",
        f"판단: {state.market_regime_reason or '-'}",
        "",
    ]
    for index, rec in enumerate(state.recommendations, start=1):
        lines.append(
            f"{index}. {rec.market} | 점수 {rec.score:.1f} | 현재가 {rec.price:,.0f} KRW | "
            f"등락률 {rec.change_rate:+.2%} | 전략 {rec.strategy_label} | 주문배수 {rec.position_size_ratio:.0%}"
        )
    lines.append("")
    lines.append("상세 이유: /why KRW-코인")
    lines.append("승인: /approve KRW-코인")
    lines.append("거절: /reject KRW-코인 사유")
    return "\n".join(lines)


def refresh_recommendations(config: Config) -> RecommendationState:
    settings = load_settings()
    client = _client(config)
    markets = get_krw_markets(client)
    registry = sync_markets(markets)
    candidates = scan_candidates(client, registry, settings)
    return generate_recommendations(client, candidates, registry, settings)


def send_recommendations(config: Config, chat_id: int | str, send: SendFn) -> None:
    settings = load_settings()
    state = refresh_recommendations(config)
    send(chat_id, _format_recommendation_list(state, settings))
    if settings.notify_approval_requests and settings.operation_mode >= 2 and state.recommendations:
        send(chat_id, format_recommendation_message(state.recommendations[0], rank=1, buy_amount_krw=settings.buy_amount_krw))


def explain_recommendation(market: str) -> str:
    rec = find_recommendation(market)
    if rec is None:
        return f"{market} 추천 정보가 없습니다. 먼저 /recommend 또는 대시보드 추천 갱신을 실행해 주세요."
    return format_recommendation_message(rec, rank=1, buy_amount_krw=load_settings().buy_amount_krw)


def reject_recommendation(market: str, reason: str = "") -> str:
    state = load_recommendation_state()
    found = False
    for rec in state.recommendations:
        if rec.market == market:
            rec.rejected = True
            rec.user_reason = reason
            found = True
    state.last_decision = f"{market} 거절: {reason or '사유 없음'}"
    save_recommendation_state(state)
    append_history("reject", {"market": market, "reason": reason})
    return f"{market} 추천을 거절로 기록했습니다. 사유: {reason or '사유 없음'}" if found else f"{market} 추천 정보가 없습니다."


def approve_recommendation(config: Config, market: str) -> str:
    settings = load_settings()
    rec = find_recommendation(market)
    if rec is None:
        return f"{market} 추천 정보가 없습니다. 먼저 /recommend 또는 대시보드 추천 갱신을 실행해 주세요."
    if settings.operation_mode < 2:
        return "현재 1단계 추천 전용 모드입니다. 실제 매매를 하려면 대시보드 또는 /mode 2로 승인형 매매를 켜야 합니다."
    if settings.approval_required is False:
        return "승인 필요 설정이 꺼져 있습니다. 안전을 위해 Telegram 승인형 실제 매매에서는 승인 필요를 켜 주세요."

    registry = load_registry()
    entry = registry.get(market, CoinEntry(market=market))
    if entry.excluded or not entry.watch or not entry.allow_recommend:
        return f"{market}은 감시/추천 허용 대상이 아닙니다."
    if not entry.allow_telegram_approval:
        return f"{market}은 Telegram 승인 매매가 허용되지 않은 코인입니다."
    if settings.operation_mode >= 3 and not entry.allow_auto_trade:
        return f"{market}은 현재 그룹 정책에서 자동매매가 허용되지 않았습니다."
    if not config.real_trade_enabled:
        append_history("approve_dry_block", {"market": market, "settings": asdict(settings)})
        return "현재 DRY_RUN 또는 ENABLE_REAL_TRADE 설정 때문에 실제 주문은 차단되었습니다."

    client = _client(config)
    available_krw = client.get_available_krw()
    order_krw = min(settings.buy_amount_krw * rec.position_size_ratio, settings.per_coin_max_krw, available_krw)
    if order_krw < config.min_order_krw:
        return f"주문 금액이 최소 주문 금액보다 작아 차단했습니다. 가능 금액: {order_krw:,.0f} KRW"
    if order_krw > settings.total_capital_krw:
        return "주문 금액이 총 운용금액 설정을 초과해 차단했습니다."

    result = client.market_buy(market, order_krw)
    state = load_recommendation_state()
    for item in state.recommendations:
        if item.market == market:
            item.approved = True
    state.last_decision = f"{market} 승인 및 주문 전송"
    save_recommendation_state(state)
    append_history(
        "approve_buy",
        {
            "market": market,
            "order_krw": order_krw,
            "recommendation": asdict(rec),
            "result": result,
        },
    )
    update_state(last_order_action="BUY", last_order_result=str(result), last_market=market)
    return f"{market} 시장가 매수 주문을 전송했습니다. 금액: {order_krw:,.0f} KRW\n결과: {result}"


def set_mode(mode_text: str) -> str:
    try:
        mode = int(mode_text)
    except ValueError:
        return "운영 단계는 /mode 1, /mode 2, /mode 3, /mode 4 형식으로 입력해 주세요."
    settings = update_settings(operation_mode=mode)
    append_history("mode_change", {"mode": mode})
    return f"운영 단계를 {settings.mode_label}(으)로 변경했습니다."


def set_trading_style(style_text: str) -> str:
    aliases = {
        "보수": "conservative",
        "보수적": "conservative",
        "conservative": "conservative",
        "균형": "balanced",
        "기본": "balanced",
        "balanced": "balanced",
        "적극": "aggressive",
        "적극적": "aggressive",
        "공격": "aggressive",
        "aggressive": "aggressive",
    }
    style = aliases.get(style_text.strip().lower())
    if style not in TRADING_STYLES:
        return "거래 성향은 /style conservative, /style balanced, /style aggressive 형식으로 입력해 주세요."
    settings = update_settings(trading_style=style)
    append_history("style_change", {"style": style})
    return f"거래 성향을 {settings.style_label}(으)로 변경했습니다.\n{settings.style_description}"


def exclude_market(market: str) -> str:
    set_coin_policy(market, excluded=True, note="Telegram에서 제외")
    append_history("exclude", {"market": market})
    return f"{market}을 제외 목록에 추가했습니다."


def include_market(market: str) -> str:
    set_coin_policy(
        market,
        excluded=False,
        watch=True,
        allow_recommend=True,
        allow_telegram_approval=True,
        group="watch",
        note="Telegram에서 제외 해제",
    )
    append_history("include", {"market": market})
    return f"{market}을 다시 감시/추천 후보에 포함했습니다."


def set_group(market: str, group: str) -> str:
    set_coin_policy(market, group=group, excluded=(group == "excluded"))
    append_history("group", {"market": market, "group": group})
    return f"{market} 그룹을 {group}(으)로 변경했습니다."

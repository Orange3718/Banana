from __future__ import annotations

import pandas as pd

from coin_registry import CoinEntry
from indicators import add_indicators
from recommendation_state import Recommendation, RecommendationState, now_text, save_recommendation_state
from settings_store import TradingSettings
from strategy_router import detect_market_regime, evaluate_strategy
from upbit_client import UpbitClient


def _score_candidate(
    row: pd.Series,
    indicator_row: pd.Series,
    settings: TradingSettings,
    recent_surge_rate: float,
) -> tuple[float, list[str], list[str], str]:
    reasons: list[str] = []
    risks: list[str] = []
    score = 0.0

    trade_value = float(row["trade_value_24h"])
    change_rate = float(row["change_rate"])
    rsi = float(indicator_row["rsi"])
    close = float(indicator_row["close"])
    ma_short = float(indicator_row["ma_short"])
    ma_mid = float(indicator_row["ma_mid"])
    ma_long = float(indicator_row["ma_long"])
    volume = float(indicator_row["volume"])
    volume_ma20 = float(indicator_row["volume_ma20"])

    hard_gate_failures: list[str] = []
    if not (ma_short > ma_mid > ma_long and close > ma_long):
        hard_gate_failures.append("MA5 > MA20 > MA60 상승 배열이 아닙니다.")
    if volume_ma20 <= 0 or volume < volume_ma20 * settings.min_entry_volume_ratio:
        hard_gate_failures.append(f"현재 거래량이 평균의 {settings.min_entry_volume_ratio:.1f}배 미만입니다.")
    if not settings.min_entry_rsi <= rsi <= settings.max_entry_rsi:
        hard_gate_failures.append(f"RSI가 진입 범위 {settings.min_entry_rsi:.0f}~{settings.max_entry_rsi:.0f} 밖입니다.")
    if not settings.min_entry_change_rate <= change_rate <= settings.max_entry_change_rate:
        hard_gate_failures.append(
            f"당일 등락률이 진입 범위 {settings.min_entry_change_rate:+.1%}~{settings.max_entry_change_rate:+.1%} 밖입니다."
        )
    if recent_surge_rate >= settings.max_recent_surge_rate:
        hard_gate_failures.append(f"최근 10분 상승률이 {settings.max_recent_surge_rate:.1%} 이상입니다.")
    if hard_gate_failures:
        return 0.0, [], hard_gate_failures, "진입 제외"

    liquidity_score = min(30.0, trade_value / max(settings.effective_min_24h_trade_value_krw(), 1.0) * 10.0)
    score += liquidity_score
    if liquidity_score >= 20:
        reasons.append("24시간 거래대금이 충분해 체결 가능성이 높습니다.")

    if close > ma_long and ma_short > ma_mid:
        score += 25
        reasons.append("가격이 장기 이동평균 위에 있고 단기 추세가 중기 추세보다 강합니다.")
        trend = "상승 우위"
    elif close > ma_long:
        score += 12
        reasons.append("가격이 장기 이동평균 위에 있어 큰 추세는 유지 중입니다.")
        trend = "중립 이상"
    else:
        risks.append("가격이 장기 이동평균 아래에 있어 추세 위험이 있습니다.")
        trend = "약세"

    if volume > volume_ma20:
        score += 15
        reasons.append("현재 거래량이 최근 평균보다 증가했습니다.")
    else:
        risks.append("현재 거래량이 최근 평균보다 낮습니다.")

    rsi_upper = 75 if settings.trading_style == "aggressive" else 62 if settings.trading_style == "conservative" else 68
    rsi_lower = 30 if settings.trading_style == "aggressive" else 38 if settings.trading_style == "conservative" else 35
    if rsi_lower <= rsi <= rsi_upper:
        score += 15
        reasons.append("RSI가 과열 구간은 아니며 매수 검토 범위에 있습니다.")
    elif rsi > 75:
        score -= 12
        risks.append("RSI가 높아 단기 과열 가능성이 있습니다.")
    elif rsi < 30:
        score -= 4
        risks.append("RSI가 낮아 하락 추세가 이어질 수 있습니다.")

    change_upper = 0.12 if settings.trading_style == "aggressive" else 0.05 if settings.trading_style == "conservative" else 0.08
    if 0 < change_rate < change_upper:
        score += 10
        reasons.append("당일 상승률이 양호하지만 과도한 급등은 아닙니다.")
    elif change_rate >= change_upper:
        score -= 8
        risks.append("당일 상승률이 높아 추격 매수 위험이 있습니다.")
    elif change_rate < -0.05:
        score -= 8
        risks.append("당일 하락률이 커서 추가 하락 위험이 있습니다.")

    if settings.trading_style == "conservative":
        score -= 5
        risks.append("보수적 거래 성향이 적용되어 기준을 더 엄격하게 봅니다.")

    return max(0.0, min(100.0, score)), reasons, risks, trend


def generate_recommendations(
    client: UpbitClient,
    candidates: pd.DataFrame,
    registry: dict[str, CoinEntry],
    settings: TradingSettings,
) -> RecommendationState:
    recommendations: list[Recommendation] = []
    regime = detect_market_regime(client)
    if candidates.empty:
        state = RecommendationState(
            generated_at=now_text(),
            recommendations=[],
            market_regime=regime.label,
            market_regime_reason=regime.reason,
        )
        return save_recommendation_state(state)

    for _, row in candidates.iterrows():
        market = str(row["market"])
        try:
            decision = evaluate_strategy(client, market, row, settings, regime)
        except Exception as exc:
            continue

        if not decision.matched or decision.score < settings.effective_min_recommendation_score():
            continue
        entry = registry.get(market, CoinEntry(market=market))
        recommendations.append(
            Recommendation(
                market=market,
                score=round(decision.score, 1),
                price=float(row["price"]),
                change_rate=float(row["change_rate"]),
                trade_value_24h=float(row["trade_value_24h"]),
                rsi=round(decision.rsi, 1),
                trend=decision.trend,
                reasons=decision.reasons,
                risks=decision.risks,
                group=entry.group,
                strategy_name=decision.strategy_name,
                strategy_label=decision.strategy_label,
                market_regime=regime.label,
                position_size_ratio=decision.position_size_ratio,
            )
        )

    recommendations.sort(key=lambda item: item.score, reverse=True)
    state = RecommendationState(
        generated_at=now_text(),
        recommendations=recommendations[: settings.recommendation_count],
        pending_market=recommendations[0].market if recommendations else "",
        market_regime=regime.label,
        market_regime_reason=regime.reason,
    )
    return save_recommendation_state(state)


def format_recommendation_message(rec: Recommendation, *, rank: int = 1, buy_amount_krw: float = 0.0) -> str:
    reasons = "\n".join(f"- {item}" for item in rec.reasons) or "- 추천 사유가 충분하지 않습니다."
    risks = "\n".join(f"- {item}" for item in rec.risks) or "- 특별한 위험 신호는 발견되지 않았습니다."
    effective_amount = buy_amount_krw * rec.position_size_ratio
    amount = f"{effective_amount:,.0f} KRW" if buy_amount_krw else "설정 금액"
    return (
        "[매매 승인 요청]\n\n"
        f"추천 코인: {rec.market}\n"
        f"추천 순위: {rank}위\n"
        f"추천 점수: {rec.score:.1f}/100\n"
        f"현재가: {rec.price:,.0f} KRW\n"
        f"24시간 거래대금: {rec.trade_value_24h:,.0f} KRW\n"
        f"등락률: {rec.change_rate:+.2%}\n"
        f"RSI: {rec.rsi:.1f}\n"
        f"추세: {rec.trend}\n"
        f"시장 상태: {rec.market_regime or '-'}\n"
        f"선택 전략: {rec.strategy_label}\n"
        f"주문 배수: {rec.position_size_ratio:.0%}\n"
        f"예상 진입금액: {amount}\n\n"
        "추천 이유:\n"
        f"{reasons}\n\n"
        "주의 요인:\n"
        f"{risks}\n\n"
        f"더 묻기: /why {rec.market}\n"
        f"승인: /approve {rec.market}\n"
        f"거절: /reject {rec.market} 사유"
    )

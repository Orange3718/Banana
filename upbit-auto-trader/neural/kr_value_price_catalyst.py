"""Offline KOSPI/KOSDAQ strategy research for 전략 C (KR_VALUE_PRICE_CATALYST).

No live data source, no broker connection, no order execution, no
credentials. Callers supply already-fetched fundamentals, price, and
disclosure (공시) data; this module only scores and decides.

The category weights (value 40 / price 35 / catalyst 25) and the entry/exit
rules follow MULTI_ASSET_STOCK_DESIGN.md section 17. The sub-weights inside
each category are this module's own draft split of that budget, not a
confirmed production value — same status as the rest of the design doc's
"모의 검증용 초안" numbers. Only formal disclosures back the catalyst score;
raw news headlines are intentionally out of scope here (see section 16's
research_note-only rule for unstructured news).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

DILUTION_RISK_CATEGORY = "dilution_or_governance_risk"

CATALYST_CATEGORY_WEIGHTS = {
    "earnings": 25.0,
    "supply_contract": 20.0,
    "capex": 15.0,
    "shareholder_return": 10.0,
}


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class ValueInputs:
    revenue_growth_pct: float
    operating_income_growth_pct: float
    roe_pct: float
    operating_cashflow_positive: bool
    debt_to_equity_pct: float
    planned_dilution: bool
    sector_relative_valuation_percentile: float  # 0 = 업종 내 최저평가, 100 = 최고평가


@dataclass(frozen=True)
class PriceInputs:
    close: float
    ma20: float
    ma60: float
    ma120: float
    volume: float
    avg_volume_20: float
    week52_high: float
    sector_relative_strength_pct: float  # 0~100
    gap_pct: float  # 전일 종가 대비 시가 갭의 절대값(%)
    breakout_confirmed: bool = False
    pullback_rebound_confirmed: bool = False
    trend_broken: bool = False


@dataclass(frozen=True)
class DisclosureEvent:
    stock_code: str
    category: str
    disclosed_at: datetime
    retracted_or_corrected: bool = False


@dataclass(frozen=True)
class ScoreBreakdown:
    value: float
    price: float
    catalyst: float

    @property
    def total(self) -> float:
        return self.value + self.price + self.catalyst


@dataclass(frozen=True)
class EntryThresholds:
    total_min: float = 70.0
    value_min: float = 16.0
    price_min: float = 14.0
    catalyst_min: float = 10.0


@dataclass(frozen=True)
class ExitThresholds:
    value_drop_from_entry: float = 10.0
    max_holding_days: int = 20


@dataclass(frozen=True)
class EntryDecision:
    approved: bool
    reason: str
    scores: ScoreBreakdown


@dataclass(frozen=True)
class ExitDecision:
    should_exit: bool
    reason: str


def score_value(inputs: ValueInputs) -> float:
    revenue = _clip(inputs.revenue_growth_pct / 2, 0, 10)
    operating = _clip(inputs.operating_income_growth_pct / 2, 0, 10)
    quality = (5.0 if inputs.operating_cashflow_positive else 0.0) + _clip(inputs.roe_pct / 2, 0, 5)
    valuation = _clip((100 - inputs.sector_relative_valuation_percentile) / 10, 0, 10)
    risk_penalty = _clip(inputs.debt_to_equity_pct / 20, 0, 10) + (10.0 if inputs.planned_dilution else 0.0)
    return _clip(revenue + operating + quality + valuation - risk_penalty, 0, 40)


def score_price(inputs: PriceInputs) -> float:
    if inputs.close > inputs.ma20 > inputs.ma60 > inputs.ma120:
        ma_alignment = 10.0
    elif inputs.close > inputs.ma20 > inputs.ma60:
        ma_alignment = 5.0
    else:
        ma_alignment = 0.0
    volume_increase = _clip((inputs.volume / inputs.avg_volume_20 - 1) * 10, 0, 10) if inputs.avg_volume_20 else 0.0
    distance_to_high = (
        _clip((1 - abs(inputs.week52_high - inputs.close) / inputs.week52_high) * 8, 0, 8)
        if inputs.week52_high
        else 0.0
    )
    relative_strength = _clip(inputs.sector_relative_strength_pct / 100 * 7, 0, 7)
    gap_penalty = _clip(inputs.gap_pct / 2, 0, 10)
    return _clip(ma_alignment + volume_increase + distance_to_high + relative_strength - gap_penalty, 0, 35)


def score_catalyst(events: list[DisclosureEvent], stock_code: str, as_of: datetime) -> float:
    relevant = [e for e in events if e.stock_code == stock_code and e.disclosed_at <= as_of]
    if any(e.category == DILUTION_RISK_CATEGORY and not e.retracted_or_corrected for e in relevant):
        return 0.0
    active = [e for e in relevant if e.category in CATALYST_CATEGORY_WEIGHTS and not e.retracted_or_corrected]
    if not active:
        return 0.0
    return _clip(max(CATALYST_CATEGORY_WEIGHTS[e.category] for e in active), 0, 25)


def score(
    value_inputs: ValueInputs,
    price_inputs: PriceInputs,
    events: list[DisclosureEvent],
    stock_code: str,
    as_of: datetime,
) -> ScoreBreakdown:
    return ScoreBreakdown(
        value=score_value(value_inputs),
        price=score_price(price_inputs),
        catalyst=score_catalyst(events, stock_code, as_of),
    )


def decide_entry(
    stock_code: str,
    value_inputs: ValueInputs,
    price_inputs: PriceInputs,
    events: list[DisclosureEvent],
    as_of: datetime,
    thresholds: EntryThresholds = EntryThresholds(),
) -> EntryDecision:
    breakdown = score(value_inputs, price_inputs, events, stock_code, as_of)
    matching = [e for e in events if e.stock_code == stock_code and not e.retracted_or_corrected]

    if not matching:
        return EntryDecision(False, "공시 원문과 종목코드가 일치하는 재료가 없습니다", breakdown)
    if any(e.disclosed_at > as_of for e in matching):
        return EntryDecision(False, "공시 시각이 판단 시점보다 이후입니다", breakdown)
    if any(e.category == DILUTION_RISK_CATEGORY for e in matching):
        return EntryDecision(False, "희석·지배구조 위험 공시로 재료 점수가 0점입니다", breakdown)
    if not (price_inputs.breakout_confirmed or price_inputs.pullback_rebound_confirmed):
        return EntryDecision(False, "거래량 동반 돌파 또는 눌림목 반등이 확인되지 않았습니다", breakdown)
    if breakdown.value < thresholds.value_min:
        return EntryDecision(False, "가치 영역 최소점수 미달", breakdown)
    if breakdown.price < thresholds.price_min:
        return EntryDecision(False, "가격 영역 최소점수 미달", breakdown)
    if breakdown.catalyst < thresholds.catalyst_min:
        return EntryDecision(False, "재료 영역 최소점수 미달", breakdown)
    if breakdown.total < thresholds.total_min:
        return EntryDecision(False, "총점 하한 미달", breakdown)
    return EntryDecision(True, "가치·가격·재료 조건과 거래량 확인을 모두 통과", breakdown)


def decide_exit(
    entry_value_score: float,
    current_value_score: float,
    price_inputs: PriceInputs,
    events: list[DisclosureEvent],
    stock_code: str,
    holding_days: int,
    thresholds: ExitThresholds = ExitThresholds(),
) -> ExitDecision:
    relevant = [e for e in events if e.stock_code == stock_code]
    if any(e.retracted_or_corrected for e in relevant):
        return ExitDecision(True, "공시 재료가 취소 또는 정정되었습니다")
    if entry_value_score - current_value_score >= thresholds.value_drop_from_entry:
        return ExitDecision(True, "실적 하향으로 가치점수가 급락했습니다")
    if price_inputs.trend_broken:
        return ExitDecision(True, "가격 추세가 훼손되었습니다")
    if holding_days >= thresholds.max_holding_days:
        return ExitDecision(True, "최대 보유기간에 도달했습니다")
    return ExitDecision(False, "청산 조건 미충족 (공통 손절·계좌 위험한도는 risk_manager가 별도 판단)")

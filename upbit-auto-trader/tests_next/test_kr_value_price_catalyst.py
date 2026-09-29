from datetime import datetime

from neural.kr_value_price_catalyst import (
    DisclosureEvent,
    EntryThresholds,
    ExitThresholds,
    PriceInputs,
    ValueInputs,
    decide_entry,
    decide_exit,
    score_catalyst,
    score_price,
    score_value,
)

AS_OF = datetime(2026, 9, 28, 9, 30)
BEFORE = datetime(2026, 9, 27, 15, 30)
AFTER = datetime(2026, 9, 28, 15, 30)


def strong_value():
    return ValueInputs(
        revenue_growth_pct=20,
        operating_income_growth_pct=20,
        roe_pct=10,
        operating_cashflow_positive=True,
        debt_to_equity_pct=0,
        planned_dilution=False,
        sector_relative_valuation_percentile=0,
    )


def strong_price():
    return PriceInputs(
        close=110,
        ma20=105,
        ma60=100,
        ma120=95,
        volume=2000,
        avg_volume_20=1000,
        week52_high=110,
        sector_relative_strength_pct=100,
        gap_pct=0,
        breakout_confirmed=True,
    )


def test_score_value_rewards_growth_quality_and_cheap_valuation():
    assert score_value(strong_value()) == 40


def test_score_value_penalizes_debt_and_planned_dilution():
    risky = ValueInputs(
        revenue_growth_pct=20,
        operating_income_growth_pct=20,
        roe_pct=10,
        operating_cashflow_positive=True,
        debt_to_equity_pct=200,
        planned_dilution=True,
        sector_relative_valuation_percentile=0,
    )
    assert score_value(risky) < score_value(strong_value())
    assert score_value(risky) >= 0


def test_score_price_rewards_full_ma_alignment_and_volume_surge():
    assert score_price(strong_price()) == 35


def test_score_price_penalizes_gap_and_broken_alignment():
    weak = PriceInputs(
        close=95,
        ma20=100,
        ma60=105,
        ma120=110,
        volume=800,
        avg_volume_20=1000,
        week52_high=110,
        sector_relative_strength_pct=10,
        gap_pct=8,
    )
    assert score_price(weak) < score_price(strong_price())
    assert score_price(weak) >= 0


def test_score_catalyst_uses_highest_weight_active_disclosure():
    events = [
        DisclosureEvent("005930", "capex", BEFORE),
        DisclosureEvent("005930", "earnings", BEFORE),
    ]
    assert score_catalyst(events, "005930", AS_OF) == 25


def test_score_catalyst_ignores_other_stocks_future_and_retracted_events():
    events = [
        DisclosureEvent("000660", "earnings", BEFORE),  # 다른 종목
        DisclosureEvent("005930", "earnings", AFTER),  # 판단 시점 이후
        DisclosureEvent("005930", "supply_contract", BEFORE, retracted_or_corrected=True),
    ]
    assert score_catalyst(events, "005930", AS_OF) == 0


def test_score_catalyst_zero_on_active_dilution_risk():
    events = [
        DisclosureEvent("005930", "earnings", BEFORE),
        DisclosureEvent("005930", "dilution_or_governance_risk", BEFORE),
    ]
    assert score_catalyst(events, "005930", AS_OF) == 0


def test_decide_entry_approves_when_all_conditions_met():
    events = [DisclosureEvent("005930", "earnings", BEFORE)]
    decision = decide_entry("005930", strong_value(), strong_price(), events, AS_OF)
    assert decision.approved
    assert decision.scores.total == 100


def test_decide_entry_blocks_without_matching_disclosure():
    decision = decide_entry("005930", strong_value(), strong_price(), [], AS_OF)
    assert not decision.approved
    assert "재료가 없습니다" in decision.reason


def test_decide_entry_blocks_on_future_disclosure_timing():
    events = [DisclosureEvent("005930", "earnings", AFTER)]
    decision = decide_entry("005930", strong_value(), strong_price(), events, AS_OF)
    assert not decision.approved
    assert "이후" in decision.reason


def test_decide_entry_blocks_on_dilution_risk_disclosure():
    events = [DisclosureEvent("005930", "dilution_or_governance_risk", BEFORE)]
    decision = decide_entry("005930", strong_value(), strong_price(), events, AS_OF)
    assert not decision.approved
    assert "희석" in decision.reason


def test_decide_entry_blocks_without_volume_confirmation():
    events = [DisclosureEvent("005930", "earnings", BEFORE)]
    no_volume_signal = PriceInputs(**{**strong_price().__dict__, "breakout_confirmed": False})
    decision = decide_entry("005930", strong_value(), no_volume_signal, events, AS_OF)
    assert not decision.approved
    assert "거래량" in decision.reason


def test_decide_entry_blocks_on_total_score_floor_even_if_each_category_passes():
    events = [DisclosureEvent("005930", "shareholder_return", BEFORE)]  # 10점, 재료 하한 정확히 통과
    marginal_value = ValueInputs(
        revenue_growth_pct=8,
        operating_income_growth_pct=8,
        roe_pct=6,
        operating_cashflow_positive=True,
        debt_to_equity_pct=0,
        planned_dilution=False,
        sector_relative_valuation_percentile=100,
    )  # value == 16, 정확히 하한
    marginal_price = PriceInputs(
        close=100,
        ma20=100,
        ma60=95,
        ma120=90,
        volume=2000,
        avg_volume_20=1000,
        week52_high=100,
        sector_relative_strength_pct=0,
        gap_pct=0,
        breakout_confirmed=True,
    )  # price == 18 (정렬 0 + 거래량 10 + 신고가 근접 8), 하한 14 이상
    thresholds = EntryThresholds()
    decision = decide_entry("005930", marginal_value, marginal_price, events, AS_OF, thresholds)
    assert decision.scores.value >= thresholds.value_min
    assert decision.scores.price >= thresholds.price_min
    assert decision.scores.catalyst >= thresholds.catalyst_min
    assert decision.scores.total < thresholds.total_min
    assert not decision.approved
    assert "총점" in decision.reason


def test_decide_exit_on_disclosure_retraction():
    events = [DisclosureEvent("005930", "earnings", BEFORE, retracted_or_corrected=True)]
    decision = decide_exit(30, 30, strong_price(), events, "005930", holding_days=1)
    assert decision.should_exit
    assert "취소" in decision.reason


def test_decide_exit_on_value_score_drop():
    decision = decide_exit(35, 20, strong_price(), [], "005930", holding_days=1)
    assert decision.should_exit
    assert "가치점수" in decision.reason


def test_decide_exit_on_trend_broken():
    broken = PriceInputs(**{**strong_price().__dict__, "trend_broken": True})
    decision = decide_exit(30, 30, broken, [], "005930", holding_days=1)
    assert decision.should_exit
    assert "추세" in decision.reason


def test_decide_exit_on_max_holding_period():
    thresholds = ExitThresholds(max_holding_days=5)
    decision = decide_exit(30, 30, strong_price(), [], "005930", holding_days=5, thresholds=thresholds)
    assert decision.should_exit
    assert "보유기간" in decision.reason


def test_decide_exit_holds_when_nothing_triggers():
    decision = decide_exit(30, 30, strong_price(), [], "005930", holding_days=1)
    assert not decision.should_exit

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import requests
import streamlit as st

from coin_registry import GROUP_POLICIES, CoinEntry, load_registry, save_registry, sync_markets
from config import Config
from future_architecture import APPROVAL_FLOW, DASHBOARD_TABS, OPERATION_MODES, TELEGRAM_COMMANDS
from indicators import add_indicators
from logger import setup_logger
from main import build_position
from market_scanner import get_krw_markets, scan_candidates
from notifier import korean_action, korean_reason
from notification_settings import NotificationRule, load_notification_rules, ordered_rules, save_notification_rules
from recommendation_engine import format_recommendation_message, generate_recommendations
from recommendation_state import (
    Recommendation,
    append_history,
    load_recommendation_state,
)
from risk_manager import RiskManager
from runtime_state import load_state, set_command
from settings_store import TRADING_STYLES, TradingSettings, load_settings, save_settings
from strategy import MovingAverageStrategy, Position
from telegram_decision import approve_recommendation
from trader import Trader
from upbit_client import UpbitAPIError, UpbitClient


PROJECT_DIR = Path(__file__).resolve().parent
ENV_PATH = PROJECT_DIR / ".env"
LOG_PATH = PROJECT_DIR / "logs" / "trading.log"
REAL_TRADE_CONFIRMATION = "REAL_TRADE"
DASHBOARD_APPROVAL_TEXT = "승인매수"


st.set_page_config(page_title="Upbit Auto Trader", layout="wide")

st.markdown(
    """
<style>
  [data-testid="stSidebar"] { border-right: 1px solid #e5e7eb; }
  [data-testid="stSidebar"] .stButton > button { width: 100%; }
  .parameter-strip {
    display:grid; grid-template-columns:repeat(8,minmax(110px,1fr)); gap:8px;
    margin:4px 0 18px 0;
  }
  .parameter-item { border:1px solid #e5e7eb; background:#f9fafb; padding:9px 10px; border-radius:6px; }
  .parameter-label { color:#6b7280; font-size:12px; }
  .parameter-value { color:#111827; font-size:14px; font-weight:750; margin-top:2px; white-space:normal; }
  @media (max-width: 1100px) { .parameter-strip { grid-template-columns:repeat(4,minmax(110px,1fr)); } }
</style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def get_logger():
    return setup_logger(log_dir=str(PROJECT_DIR / "logs"))


def load_config() -> Config:
    return Config.load(ENV_PATH)


def make_client(config: Config) -> UpbitClient:
    return UpbitClient(config.access_key, config.secret_key, config.base_url)


def credentials_ready(config: Config) -> bool:
    return (
        bool(config.access_key)
        and bool(config.secret_key)
        and config.access_key != "your_access_key"
        and config.secret_key != "your_secret_key"
    )


def send_telegram(config: Config, text: str) -> tuple[bool, str]:
    if not config.telegram_bot_token.strip() or not config.telegram_allowed_chat_id.strip():
        return False, "Telegram token 또는 allowed chat id가 없습니다."
    try:
        requests.post(
            f"https://api.telegram.org/bot{config.telegram_bot_token.strip()}/sendMessage",
            json={"chat_id": config.telegram_allowed_chat_id.strip(), "text": text},
            timeout=10,
        ).raise_for_status()
    except Exception as exc:
        return False, str(exc)
    return True, "Telegram 전송 완료"


def fetch_snapshot(config: Config, client: UpbitClient) -> dict[str, Any]:
    candles = client.get_candles(config.market, config.interval, config.candle_count)
    market_data = add_indicators(candles, config.ma_short, config.ma_mid, config.ma_long, config.rsi_period).dropna()
    if market_data.empty:
        raise ValueError("지표 계산 결과가 비어 있습니다. CANDLE_COUNT를 늘려 주세요.")

    current_price = client.get_current_price(config.market)
    fallback = st.session_state.get("position")
    if fallback is not None and not isinstance(fallback, Position):
        fallback = None
    position = build_position(config, client, fallback)
    if position.has_position:
        position.highest_profit_rate = max(position.highest_profit_rate, position.profit_rate(current_price))
    st.session_state.position = position

    available_krw = float(st.session_state.paper_krw) if config.dry_run else client.get_available_krw()
    total_equity = available_krw + (position.volume * current_price)
    settings = load_settings()
    signal = MovingAverageStrategy(config, settings).generate_signal(market_data, position)

    return {
        "candles": candles,
        "market_data": market_data,
        "current_price": current_price,
        "position": position,
        "available_krw": available_krw,
        "total_equity": total_equity,
        "signal": signal,
    }


def execute_strategy_once(config: Config, client: UpbitClient, snapshot: dict[str, Any]) -> dict[str, Any] | None:
    logger = get_logger()
    risk_manager = RiskManager(config)
    risk_manager.set_api_available(True)
    trader = Trader(config, client, risk_manager, logger)
    result = trader.execute_signal(
        snapshot["signal"],
        snapshot["position"],
        snapshot["available_krw"],
        snapshot["current_price"],
        snapshot["total_equity"],
    )
    if config.dry_run and result:
        if snapshot["signal"].get("action") == "BUY":
            st.session_state.paper_krw = max(0.0, float(st.session_state.paper_krw) - float(result.get("amount", 0)))
        elif snapshot["signal"].get("action") == "SELL":
            st.session_state.paper_krw = float(st.session_state.paper_krw) + float(result.get("volume", 0)) * snapshot["current_price"]
    return result


def read_logs(lines: int = 80) -> str:
    if not LOG_PATH.exists():
        return "아직 로그 파일이 없습니다."
    return "\n".join(LOG_PATH.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])


def load_trade_history(limit: int = 500) -> pd.DataFrame:
    history_path = PROJECT_DIR / "trade_history.jsonl"
    if not history_path.exists():
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for line in history_path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except Exception:
            continue

        event = str(item.get("event", ""))
        result = item.get("final_result") or item.get("result") or {}
        recommendation = item.get("recommendation") or {}
        if not isinstance(result, dict):
            result = {}
        if not isinstance(recommendation, dict):
            recommendation = {}

        rows.append(
            {
                "시간": item.get("time", ""),
                "유형": event,
                "마켓": item.get("market") or item.get("top_market") or recommendation.get("market", ""),
                "상태": result.get("state", ""),
                "주문금액": str(item.get("order_krw") or item.get("buy_amount_krw") or result.get("price", "")),
                "체결수량": str(result.get("executed_volume", "")),
                "수수료": str(result.get("paid_fee", "")),
                "추천점수": str(recommendation.get("score") or item.get("score", "")),
                "사유": item.get("reason", ""),
                "주문번호": result.get("uuid", ""),
            }
        )

    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("시간", ascending=False).reset_index(drop=True)


def fetch_portfolio(config: Config, client: UpbitClient) -> pd.DataFrame:
    if config.dry_run or not credentials_ready(config):
        return pd.DataFrame(
            [
                {
                    "자산": "KRW",
                    "보유수량": float(st.session_state.get("paper_krw", config.paper_initial_krw)),
                    "사용가능수량": float(st.session_state.get("paper_krw", config.paper_initial_krw)),
                    "주문중수량": 0.0,
                    "평균매수가": 1.0,
                    "현재가": 1.0,
                    "평가금액": float(st.session_state.get("paper_krw", config.paper_initial_krw)),
                    "매수원금": float(st.session_state.get("paper_krw", config.paper_initial_krw)),
                    "손익": 0.0,
                    "손익률": 0.0,
                    "비중": 1.0,
                    "가격상태": "정상",
                    "가격기준": "KRW 현금",
                }
            ]
        )

    accounts = client.get_accounts()
    raw_rows: list[dict[str, Any]] = []
    markets: list[str] = []
    for account in accounts:
        currency = str(account.get("currency", ""))
        balance = float(account.get("balance", 0) or 0)
        locked = float(account.get("locked", 0) or 0)
        amount = balance + locked
        if amount <= 0:
            continue
        avg_buy_price = float(account.get("avg_buy_price", 0) or 0)
        row = {
            "자산": currency,
            "보유수량": amount,
            "사용가능수량": balance,
            "주문중수량": locked,
            "평균매수가": avg_buy_price,
            "현재가": 1.0 if currency == "KRW" else 0.0,
        }
        raw_rows.append(row)
        if currency != "KRW":
            markets.append(f"KRW-{currency}")

    price_map: dict[str, float] = {}
    price_source_map: dict[str, str] = {}
    valid_markets: set[str] = set()
    if markets:
        try:
            valid_markets = {
                str(item.get("market", ""))
                for item in client._request("GET", "/v1/market/all", {"isDetails": "false"})
            }
            query_markets: set[str] = set()
            conversion_routes: dict[str, tuple[str, str | None]] = {}
            for market in markets:
                currency = market.split("-", 1)[1]
                direct = f"KRW-{currency}"
                via_btc = f"BTC-{currency}"
                via_usdt = f"USDT-{currency}"
                if direct in valid_markets:
                    conversion_routes[market] = (direct, None)
                    query_markets.add(direct)
                elif via_btc in valid_markets and "KRW-BTC" in valid_markets:
                    conversion_routes[market] = (via_btc, "KRW-BTC")
                    query_markets.update({via_btc, "KRW-BTC"})
                elif via_usdt in valid_markets and "KRW-USDT" in valid_markets:
                    conversion_routes[market] = (via_usdt, "KRW-USDT")
                    query_markets.update({via_usdt, "KRW-USDT"})

            ticker_map: dict[str, float] = {}
            query_market_list = sorted(query_markets)
            for index in range(0, len(query_market_list), 80):
                batch = query_market_list[index : index + 80]
                if not batch:
                    continue
                tickers = client._request("GET", "/v1/ticker", {"markets": ",".join(batch)})
                ticker_map.update({str(item.get("market", "")): float(item.get("trade_price", 0) or 0) for item in tickers})

            for target_market, (quote_market, bridge_market) in conversion_routes.items():
                quote_price = ticker_map.get(quote_market, 0.0)
                bridge_price = ticker_map.get(bridge_market, 1.0) if bridge_market else 1.0
                converted_price = quote_price * bridge_price
                if converted_price > 0:
                    price_map[target_market] = converted_price
                    price_source_map[target_market] = quote_market if bridge_market is None else f"{quote_market} × {bridge_market}"
        except Exception:
            price_map = {}
            price_source_map = {}

        for market in sorted(markets):
            if price_map.get(market, 0.0) > 0 or market not in valid_markets:
                continue
            try:
                price_map[market] = float(client.get_current_price(market))
                price_source_map[market] = market
            except Exception:
                continue

    rows: list[dict[str, Any]] = []
    total_value = 0.0
    for row in raw_rows:
        currency = str(row["자산"])
        market = f"KRW-{currency}"
        current_price = 1.0 if currency == "KRW" else price_map.get(market, 0.0)
        amount = float(row["보유수량"])
        avg_buy_price = float(row["평균매수가"])
        value = amount * current_price if current_price > 0 else 0.0
        cost = amount * avg_buy_price if currency != "KRW" and avg_buy_price > 0 else value
        profit = value - cost if current_price > 0 else 0.0
        profit_rate = profit / cost if cost > 0 and currency != "KRW" and current_price > 0 else 0.0
        total_value += value
        rows.append(
            {
                **row,
                "현재가": current_price,
                "평가금액": value,
                "매수원금": cost,
                "손익": profit,
                "손익률": profit_rate,
                "가격상태": "정상" if currency == "KRW" or current_price > 0 else "KRW 마켓 없음/조회 실패",
                "가격기준": "KRW 현금" if currency == "KRW" else price_source_map.get(market, "환산 경로 없음"),
            }
        )

    if total_value <= 0:
        return pd.DataFrame(rows)
    for row in rows:
        row["비중"] = float(row["평가금액"]) / total_value
    return pd.DataFrame(rows).sort_values("평가금액", ascending=False).reset_index(drop=True)


def portfolio_summary(portfolio: pd.DataFrame) -> dict[str, float]:
    if portfolio.empty:
        return {
            "total_value": 0.0,
            "cash_total": 0.0,
            "cash_available": 0.0,
            "invested_value": 0.0,
            "coin_cost": 0.0,
            "profit": 0.0,
            "profit_rate": 0.0,
            "holding_count": 0.0,
        }
    cash_rows = portfolio[portfolio["자산"] == "KRW"]
    coin_rows = portfolio[portfolio["자산"] != "KRW"]
    valued_coin_rows = coin_rows[coin_rows["현재가"] > 0]
    total_value = float(portfolio["평가금액"].sum())
    cash_total = float(cash_rows["평가금액"].sum())
    cash_available = float(cash_rows["사용가능수량"].sum()) if "사용가능수량" in cash_rows else cash_total
    invested_value = float(valued_coin_rows["평가금액"].sum())
    coin_cost = float(valued_coin_rows["매수원금"].sum())
    profit = invested_value - coin_cost
    return {
        "total_value": total_value,
        "cash_total": cash_total,
        "cash_available": cash_available,
        "invested_value": invested_value,
        "coin_cost": coin_cost,
        "profit": profit,
        "profit_rate": profit / coin_cost if coin_cost > 0 else 0.0,
        "holding_count": float(len(coin_rows)),
    }


def status_badge(label: str, value: str, kind: str = "info") -> None:
    colors = {
        "safe": ("#0f766e", "#ecfdf5"),
        "warn": ("#b45309", "#fffbeb"),
        "danger": ("#b91c1c", "#fef2f2"),
        "info": ("#1d4ed8", "#eff6ff"),
        "neutral": ("#374151", "#f9fafb"),
    }
    border, bg = colors.get(kind, colors["info"])
    st.markdown(
        f"""
<div style="border:1px solid {border};background:{bg};padding:12px;border-radius:8px;margin-bottom:8px">
  <div style="font-size:13px;color:#555">{label}</div>
  <div style="font-size:20px;font-weight:700;color:{border}">{value}</div>
</div>
        """,
        unsafe_allow_html=True,
    )


def format_krw(value: float) -> str:
    return f"{value:,.0f}원"


def format_percent(value: float) -> str:
    return f"{value:+.2%}"


def render_portfolio_overview(portfolio: pd.DataFrame) -> None:
    summary = portfolio_summary(portfolio)
    total_value = summary["total_value"]
    total_profit = summary["profit"]
    total_profit_rate = summary["profit_rate"]
    cash_value = summary["cash_total"]
    coin_count = int(summary["holding_count"])
    profit_color = "#c2410c" if total_profit >= 0 else "#2563eb"

    st.markdown(
        f"""
<div style="padding:18px 0 8px 0">
  <div style="font-size:14px;color:#6b7280">총 자산</div>
  <div style="font-size:42px;font-weight:800;letter-spacing:0;color:#111827">{format_krw(total_value)}</div>
  <div style="font-size:15px;color:{profit_color};font-weight:700">
    평가손익 {total_profit:+,.0f}원 ({total_profit_rate:+.2%})
  </div>
  <div style="font-size:13px;color:#6b7280;margin-top:4px">
    보유 코인 {coin_count}개 · 현금 {format_krw(cash_value)}
  </div>
</div>
        """,
        unsafe_allow_html=True,
    )


def render_portfolio_charts(portfolio: pd.DataFrame) -> None:
    chart_source = portfolio[(portfolio["평가금액"] > 0) & (portfolio["가격상태"] == "정상")].copy()
    if chart_source.empty:
        st.info("그래프로 표시할 평가 자산이 없습니다.")
        return

    chart_source["비중표시"] = chart_source["비중"].map(lambda value: f"{value:.1%}")
    left, right = st.columns([1, 1.15])
    with left:
        st.caption("자산 비중")
        st.vega_lite_chart(
            chart_source,
            {
                "height": 285,
                "mark": {"type": "arc", "innerRadius": 72, "outerRadius": 125},
                "encoding": {
                    "theta": {"field": "평가금액", "type": "quantitative"},
                    "color": {
                        "field": "자산",
                        "type": "nominal",
                        "scale": {"scheme": "tableau20"},
                        "legend": {"orient": "bottom", "columns": 3},
                    },
                    "tooltip": [
                        {"field": "자산", "type": "nominal"},
                        {"field": "평가금액", "type": "quantitative", "format": ",.0f"},
                        {"field": "비중표시", "type": "nominal", "title": "비중"},
                    ],
                },
            },
            use_container_width=True,
        )
    with right:
        st.caption("평가금액 순위")
        st.bar_chart(chart_source.set_index("자산")[["평가금액"]], use_container_width=True, height=285)


def render_asset_cards(portfolio: pd.DataFrame) -> None:
    st.caption("보유 자산")
    display_rows = portfolio[(portfolio["평가금액"] > 0) & (portfolio["가격상태"] == "정상")].head(12)
    for row in display_rows.to_dict("records"):
        profit = float(row["손익"])
        profit_rate = float(row["손익률"])
        color = "#c2410c" if profit >= 0 else "#2563eb"
        st.markdown(
            f"""
<div style="display:grid;grid-template-columns:1fr auto;gap:10px;align-items:center;
            padding:12px 2px;border-bottom:1px solid #eef2f7">
  <div>
    <div style="font-size:16px;font-weight:800;color:#111827">{row['자산']}</div>
    <div style="font-size:13px;color:#6b7280">비중 {float(row['비중']):.1%} · 보유 {float(row['보유수량']):,.8g}</div>
  </div>
  <div style="text-align:right">
    <div style="font-size:16px;font-weight:800;color:#111827">{format_krw(float(row['평가금액']))}</div>
    <div style="font-size:13px;color:{color};font-weight:700">{profit:+,.0f}원 ({profit_rate:+.2%})</div>
  </div>
</div>
            """,
            unsafe_allow_html=True,
        )


def render_recent_trade_summary() -> None:
    history = load_trade_history()
    if history.empty:
        st.info("최근 거래 이력이 없습니다.")
        return
    recent = history[history["유형"].isin(["auto_buy", "auto_sell", "approve_buy", "strategy_order", "order_fill_check", "auto_buy_blocked", "auto_sell_blocked"])].head(5)
    if recent.empty:
        st.info("최근 매수/보류 이력이 없습니다.")
        return
    st.dataframe(recent, use_container_width=True, hide_index=True)


def action_help() -> None:
    st.markdown(
        """
색상 기준:
- 초록색: 안전 확인 또는 조회 기능입니다.
- 파란색: 설정 저장, 추천 갱신처럼 상태를 바꾸지만 주문은 보내지 않는 기능입니다.
- 노란색: 주의가 필요한 기능입니다.
- 빨간색: 실제 주문 또는 긴급 제어처럼 강한 효과가 있는 기능입니다.
        """
    )


def render_live_tab(config: Config, client: UpbitClient) -> None:
    state = load_state()
    running_state = "킬 스위치" if state.kill_switch else ("일시정지" if state.paused else "실행 중")
    mode_kind = "danger" if config.real_trade_enabled else "safe"
    st.subheader("전체 자산")
    queried_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.caption(f"업비트 계정과 KRW 시세를 직접 조회한 전체 자산입니다. 조회 시각 {queried_at}")

    try:
        portfolio = fetch_portfolio(config, client)
    except Exception as exc:
        st.error(f"전체 자산 조회 실패: {exc}")
        portfolio = pd.DataFrame()

    if not portfolio.empty:
        summary = portfolio_summary(portfolio)
        total_value = summary["total_value"]
        cash_value = summary["cash_available"]
        invested_value = summary["invested_value"]
        total_cost = summary["coin_cost"]
        total_profit = summary["profit"]
        total_profit_rate = summary["profit_rate"]
        holding_count = int(summary["holding_count"])
        missing_price_count = int(((portfolio["자산"] != "KRW") & (portfolio["현재가"] <= 0)).sum())
    else:
        total_value = state.total_equity
        cash_value = state.available_krw
        invested_value = max(0.0, total_value - cash_value)
        total_profit = 0.0
        total_profit_rate = 0.0
        holding_count = int(state.position_volume or 0)
        missing_price_count = 0

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        status_badge("운영 상태", running_state, "danger" if state.kill_switch else "safe" if state.paused else "warn")
    with col2:
        status_badge("실거래", "ON" if config.real_trade_enabled else "OFF", mode_kind)
    with col3:
        status_badge("현재 단계", state.last_step or "-", "info")
    with col4:
        status_badge("운용 범위", "업비트 KRW 마켓 전체", "neutral")
    with col5:
        status_badge("마지막 신호", korean_action(state.last_signal), "info")

    cols = st.columns(6)
    cols[0].metric("총 자산", f"{total_value:,.0f} KRW" if total_value else "-")
    cols[1].metric("사용 가능 KRW", f"{cash_value:,.0f}" if cash_value else "-")
    cols[2].metric("투자 중 금액", f"{invested_value:,.0f}" if invested_value else "-")
    cols[3].metric("평가손익", f"{total_profit:+,.0f}" if total_cost else "-")
    cols[4].metric("평가손익률", f"{total_profit_rate:+.2%}" if total_cost else "-")
    cols[5].metric("보유 코인 수", f"{holding_count:,}")
    st.info(
        "최근 판단: "
        f"{korean_action(state.last_signal)} / {korean_reason(state.last_signal_reason) if state.last_signal_reason else '-'} "
        f"· 워커 갱신 {state.last_heartbeat or '-'}"
    )

    if missing_price_count:
        st.warning(
            f"보유 코인 {holding_count}개 중 {missing_price_count}개는 업비트에서 KRW·BTC·USDT 환산 경로를 찾지 못해 "
            "총 자산과 손익 계산에서 제외했습니다. 보유 코인 메뉴에는 해당 자산도 숨김 없이 표시됩니다."
        )

    if not portfolio.empty and state.total_equity > 0:
        state_gap = abs(total_value - state.total_equity) / max(total_value, 1.0)
        if state_gap >= 0.03:
            st.warning(
                f"실시간 계정 평가액과 워커 저장값의 차이가 {state_gap:.1%}입니다. "
                "화면의 자산 금액은 현재 업비트 조회값을 우선하며, 워커 값은 마지막 판단 시점 참고값입니다."
            )

    if portfolio.empty:
        st.info("표시할 자산이 없습니다.")
    else:
        render_portfolio_overview(portfolio)
        render_portfolio_charts(portfolio)
        left, right = st.columns([1.1, 1])
        with left:
            render_asset_cards(portfolio)
        with right:
            st.caption("최근 매매/보류")
            render_recent_trade_summary()
        with st.expander("자산 상세 표", expanded=False):
            display = portfolio.copy()
            display["평가금액"] = display["평가금액"].map(lambda value: f"{value:,.0f}")
            display["매수원금"] = display["매수원금"].map(lambda value: f"{value:,.0f}")
            display["손익"] = display["손익"].map(lambda value: f"{value:+,.0f}")
            display["손익률"] = display["손익률"].map(lambda value: f"{value:+.2%}")
            display["비중"] = display["비중"].map(lambda value: f"{value:.1%}")
            st.dataframe(display, use_container_width=True, hide_index=True)


def render_holdings_tab(config: Config, client: UpbitClient, settings: TradingSettings) -> None:
    st.subheader("보유 코인")
    st.caption("코인별 실시간 평가와 현재 자동매매 정책, 손절·익절 기준을 한 행에서 확인합니다.")
    try:
        portfolio = fetch_portfolio(config, client)
    except Exception as exc:
        st.error(f"보유 코인 조회 실패: {exc}")
        return

    coins = portfolio[portfolio["자산"] != "KRW"].copy()
    if coins.empty:
        st.info("현재 보유 중인 코인이 없습니다.")
        return

    registry = load_registry()
    rows: list[dict[str, Any]] = []
    for item in coins.to_dict("records"):
        market = f"KRW-{item['자산']}"
        entry = registry.get(market, CoinEntry(market=market))
        avg_price = float(item["평균매수가"])
        profit_rate = float(item["손익률"])
        stop_price = avg_price * (1 - settings.stop_loss_rate) if avg_price > 0 else 0.0
        tp1_price = avg_price * (1 + settings.take_profit_rate_1) if avg_price > 0 else 0.0
        tp2_price = avg_price * (1 + settings.take_profit_rate_2) if avg_price > 0 else 0.0
        if entry.excluded:
            next_action = "제외 코인 - 자동매매 안 함"
        elif not entry.allow_auto_trade:
            next_action = "자동매매 미허용"
        elif profit_rate <= -settings.stop_loss_rate:
            next_action = "손절 조건 도달"
        elif profit_rate >= settings.take_profit_rate_2:
            next_action = "2차 익절 조건 도달"
        elif profit_rate >= settings.take_profit_rate_1:
            next_action = "1차 익절 조건 도달"
        else:
            next_action = f"손절 {stop_price:,.4g} / 1차익절 {tp1_price:,.4g}"
        rows.append(
            {
                "마켓": market,
                "이름": entry.korean_name or item["자산"],
                "보유수량": float(item["보유수량"]),
                "현재가": float(item["현재가"]),
                "평균매수가": avg_price,
                "평가금액": float(item["평가금액"]),
                "손익": float(item["손익"]),
                "손익률": profit_rate * 100,
                "그룹": entry.group,
                "자동매매": "허용" if entry.allow_auto_trade and not entry.excluded else "차단",
                "손절가": stop_price,
                "1차익절가": tp1_price,
                "2차익절가": tp2_price,
                "다음 조건": next_action,
                "가격상태": item["가격상태"],
                "가격기준": item.get("가격기준", ""),
            }
        )
    holdings = pd.DataFrame(rows).sort_values("평가금액", ascending=False)
    st.dataframe(
        holdings,
        use_container_width=True,
        hide_index=True,
        column_config={
            "보유수량": st.column_config.NumberColumn(format="%.8f"),
            "현재가": st.column_config.NumberColumn(format="₩ %.4g"),
            "평균매수가": st.column_config.NumberColumn(format="₩ %.4g"),
            "평가금액": st.column_config.NumberColumn(format="₩ %,.0f"),
            "손익": st.column_config.NumberColumn(format="₩ %,.0f"),
            "손익률": st.column_config.NumberColumn(format="%.2f %%"),
            "손절가": st.column_config.NumberColumn(format="₩ %.4g"),
            "1차익절가": st.column_config.NumberColumn(format="₩ %.4g"),
            "2차익절가": st.column_config.NumberColumn(format="₩ %.4g"),
        },
    )
    st.caption("손익률과 손절·익절 기준은 현재 설정을 적용한 값입니다. 자동매매 차단 코인은 조건에 도달해도 주문하지 않습니다.")


def render_strategy_diagnostics_tab(config: Config, client: UpbitClient) -> None:
    st.subheader("전략 진단")
    st.caption(f"이 화면은 전체 자산이 아니라 `.env`의 전략 진단 마켓 {config.market}만 분석합니다.")
    try:
        snapshot = fetch_snapshot(config, client)
    except Exception as exc:
        st.error(f"시장 데이터 조회 실패: {exc}")
        return
    latest = snapshot["market_data"].iloc[-1]
    signal = snapshot["signal"]
    cols = st.columns(4)
    cols[0].metric(f"{config.market} 현재가", f"{snapshot['current_price']:,.0f} KRW")
    cols[1].metric(f"MA{config.ma_short}", f"{latest['ma_short']:,.0f}")
    cols[2].metric(f"MA{config.ma_mid}", f"{latest['ma_mid']:,.0f}")
    cols[3].metric("RSI", f"{latest['rsi']:.1f}")
    st.info(f"진단 전략 신호: {korean_action(str(signal.get('action')))} / {korean_reason(str(signal.get('reason')))}")
    st.line_chart(snapshot["market_data"].tail(120).set_index(pd.to_datetime(snapshot["market_data"].tail(120)["timestamp"]))[["close", "ma_short", "ma_mid", "ma_long"]])


def render_settings_tab(settings: TradingSettings) -> TradingSettings:
    st.subheader("파라미터 설정")
    st.info("여기에서 저장한 값은 trading_settings.json에 저장됩니다. .env의 API 키는 수정하지 않습니다.")
    with st.form("settings_form"):
        col1, col2, col3, col4 = st.columns(4)
        operation_mode = col1.selectbox(
            "운영 단계",
            [1, 2, 3, 4],
            index=max(0, settings.operation_mode - 1),
            format_func=lambda value: {
                1: "1단계 추천 전용",
                2: "2단계 승인형 실제 추천 매매",
                3: "3단계 그룹 제한 자동매매",
                4: "4단계 완전 자동 운영",
            }[value],
        )
        style_keys = list(TRADING_STYLES.keys())
        trading_style = col2.selectbox(
            "거래 성향",
            style_keys,
            index=style_keys.index(settings.trading_style) if settings.trading_style in style_keys else 1,
            format_func=lambda value: TRADING_STYLES[value]["label"],
        )
        approval_required = col3.checkbox("실제 진입 전 Telegram 승인 필수", value=settings.approval_required)
        recommendation_enabled = col4.checkbox("자동 추천 사용", value=settings.recommendation_enabled)
        st.caption(f"선택한 성향: {TRADING_STYLES[trading_style]['description']}")

        col1, col2, col3, col4 = st.columns(4)
        include_btc = col1.checkbox("BTC 포함", value=settings.include_btc)
        recommendation_count = col2.number_input("추천 코인 수", 1, 20, settings.recommendation_count)
        scanner_market_limit = col3.number_input("스캔 코인 수", 5, 100, settings.scanner_market_limit)
        min_recommendation_score = col4.number_input("최소 추천 점수", 0.0, 100.0, settings.min_recommendation_score, step=1.0)

        col1, col2 = st.columns(2)
        min_24h_trade_value_krw = col1.number_input("최소 24시간 거래대금 KRW", 0.0, 1_000_000_000_000.0, settings.min_24h_trade_value_krw, step=100_000_000.0)
        max_change_rate_abs = col2.number_input("최대 절대 등락률", 0.01, 1.0, settings.max_change_rate_abs, step=0.01, format="%.2f")

        col1, col2, col3 = st.columns(3)
        total_capital_krw = col1.number_input("총 운용금액 KRW", 0.0, 10_000_000_000.0, settings.total_capital_krw, step=10_000.0)
        buy_amount_krw = col2.number_input("1회 매수 금액 KRW", 0.0, 10_000_000_000.0, settings.buy_amount_krw, step=5_000.0)
        per_coin_max_krw = col3.number_input("코인당 최대 투자금 KRW", 0.0, 10_000_000_000.0, settings.per_coin_max_krw, step=10_000.0)

        col1, col2, col3, col4, col5 = st.columns(5)
        max_positions = col1.number_input(
            "자동매매 최대 보유 종목",
            1,
            50,
            settings.max_positions,
            help="자동매매가 새로 진입할 수 있는 코인 수입니다. 기존 일반 보유자산을 강제로 매도하지 않습니다.",
        )
        max_daily_trades = col2.number_input("하루 최대 신규매수", 1, 100, settings.max_daily_trades)
        stop_loss_rate = col3.number_input("손절률", 0.001, 1.0, settings.stop_loss_rate, step=0.005, format="%.3f")
        take_profit_rate_1 = col4.number_input("1차 익절률", 0.001, 1.0, settings.take_profit_rate_1, step=0.005, format="%.3f")
        take_profit_rate_2 = col5.number_input("2차 익절률", 0.001, 1.0, settings.take_profit_rate_2, step=0.005, format="%.3f")

        col1, col2, col3, col4 = st.columns(4)
        trailing_stop_rate = col1.number_input("고점 대비 매도폭", 0.001, 1.0, settings.trailing_stop_rate, step=0.005, format="%.3f")
        trailing_activation_rate = col2.number_input("추적매도 시작 수익률", 0.001, 1.0, settings.trailing_activation_rate, step=0.005, format="%.3f")
        min_cash_reserve_krw = col3.number_input("최소 보유 현금 KRW", 0.0, 10_000_000_000.0, settings.min_cash_reserve_krw, step=10_000.0)
        min_cash_reserve_ratio = col4.number_input("최소 현금 비율", 0.0, 1.0, settings.min_cash_reserve_ratio, step=0.05, format="%.2f")
        max_daily_loss_rate = st.number_input(
            "하루 계좌 손실 제한",
            0.001,
            1.0,
            settings.max_daily_loss_rate,
            step=0.005,
            format="%.3f",
            help="당일 최초 계좌 평가금액보다 이 비율 이상 감소하면 그날 신규매수를 중단합니다.",
        )

        col1, col2, col3, col4 = st.columns(4)
        loss_cooldown_minutes = col1.number_input("손실 후 재진입 대기(분)", 0, 1440, settings.loss_cooldown_minutes, step=30)
        profit_cooldown_minutes = col2.number_input("수익 후 재진입 대기(분)", 0, 1440, settings.profit_cooldown_minutes, step=30)
        max_consecutive_losses = col3.number_input("연속 손실 정지 기준", 1, 20, settings.max_consecutive_losses)
        loss_pause_minutes = col4.number_input("연속 손실 정지 시간(분)", 1, 1440, settings.loss_pause_minutes, step=30)

        with st.expander("자동매수 필수 진입 조건", expanded=False):
            col1, col2, col3 = st.columns(3)
            min_entry_rsi = col1.number_input("최소 RSI", 0.0, 100.0, settings.min_entry_rsi, step=1.0)
            max_entry_rsi = col2.number_input("최대 RSI", 0.0, 100.0, settings.max_entry_rsi, step=1.0)
            min_entry_volume_ratio = col3.number_input("평균 대비 최소 거래량 배수", 0.1, 10.0, settings.min_entry_volume_ratio, step=0.1)
            col1, col2, col3 = st.columns(3)
            min_entry_change_rate = col1.number_input("최소 당일 등락률", -0.99, 0.99, settings.min_entry_change_rate, step=0.005, format="%.3f")
            max_entry_change_rate = col2.number_input("최대 당일 등락률", -0.99, 0.99, settings.max_entry_change_rate, step=0.005, format="%.3f")
            max_recent_surge_rate = col3.number_input("최근 10분 최대 상승률", 0.001, 1.0, settings.max_recent_surge_rate, step=0.005, format="%.3f")

        with st.expander("복합전략 사용 여부 / 주문 비중", expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            enable_trend_confirmation = col1.checkbox("다중 조건 추세", value=settings.enable_trend_confirmation)
            enable_trend_pullback = col2.checkbox("추세 눌림목", value=settings.enable_trend_pullback)
            enable_volatility_breakout = col3.checkbox("변동성 돌파", value=settings.enable_volatility_breakout)
            enable_mean_reversion = col4.checkbox("횡보장 평균회귀", value=settings.enable_mean_reversion)
            col1, col2, col3, col4 = st.columns(4)
            trend_position_size_ratio = col1.number_input("추세 주문배수", 0.05, 1.0, settings.trend_position_size_ratio, step=0.05)
            pullback_position_size_ratio = col2.number_input("눌림목 주문배수", 0.05, 1.0, settings.pullback_position_size_ratio, step=0.05)
            breakout_position_size_ratio = col3.number_input("돌파 주문배수", 0.05, 1.0, settings.breakout_position_size_ratio, step=0.05)
            mean_reversion_position_size_ratio = col4.number_input("평균회귀 주문배수", 0.05, 1.0, settings.mean_reversion_position_size_ratio, step=0.05)

        col1, col2, col3 = st.columns(3)
        notify_recommendations = col1.checkbox("추천 알림", value=settings.notify_recommendations)
        notify_approval_requests = col2.checkbox("승인 요청 알림", value=settings.notify_approval_requests)
        notify_order_results = col3.checkbox("주문 결과 알림", value=settings.notify_order_results)
        periodic_report_minutes = st.number_input("주기 리포트 간격(분)", 5, 1440, settings.periodic_report_minutes)
        daily_review_time = st.text_input("일일 복기 시간", value=settings.daily_review_time)

        submitted = st.form_submit_button("설정 저장", type="primary", use_container_width=True)
    new_settings = TradingSettings(
        operation_mode=operation_mode,
        trading_style=trading_style,
        approval_required=approval_required,
        recommendation_enabled=recommendation_enabled,
        include_btc=include_btc,
        recommendation_count=int(recommendation_count),
        scanner_market_limit=int(scanner_market_limit),
        min_recommendation_score=float(min_recommendation_score),
        min_24h_trade_value_krw=float(min_24h_trade_value_krw),
        max_change_rate_abs=float(max_change_rate_abs),
        total_capital_krw=float(total_capital_krw),
        buy_amount_krw=float(buy_amount_krw),
        per_coin_max_krw=float(per_coin_max_krw),
        max_positions=int(max_positions),
        max_daily_trades=int(max_daily_trades),
        stop_loss_rate=float(stop_loss_rate),
        take_profit_rate_1=float(take_profit_rate_1),
        take_profit_rate_2=float(take_profit_rate_2),
        trailing_stop_rate=float(trailing_stop_rate),
        trailing_activation_rate=float(trailing_activation_rate),
        min_cash_reserve_krw=float(min_cash_reserve_krw),
        min_cash_reserve_ratio=float(min_cash_reserve_ratio),
        max_daily_loss_rate=float(max_daily_loss_rate),
        loss_cooldown_minutes=int(loss_cooldown_minutes),
        profit_cooldown_minutes=int(profit_cooldown_minutes),
        max_consecutive_losses=int(max_consecutive_losses),
        loss_pause_minutes=int(loss_pause_minutes),
        min_entry_rsi=float(min_entry_rsi),
        max_entry_rsi=float(max_entry_rsi),
        min_entry_volume_ratio=float(min_entry_volume_ratio),
        min_entry_change_rate=float(min_entry_change_rate),
        max_entry_change_rate=float(max_entry_change_rate),
        max_recent_surge_rate=float(max_recent_surge_rate),
        enable_trend_confirmation=enable_trend_confirmation,
        enable_trend_pullback=enable_trend_pullback,
        enable_volatility_breakout=enable_volatility_breakout,
        enable_mean_reversion=enable_mean_reversion,
        trend_position_size_ratio=float(trend_position_size_ratio),
        pullback_position_size_ratio=float(pullback_position_size_ratio),
        breakout_position_size_ratio=float(breakout_position_size_ratio),
        mean_reversion_position_size_ratio=float(mean_reversion_position_size_ratio),
        notify_recommendations=notify_recommendations,
        notify_approval_requests=notify_approval_requests,
        notify_order_results=notify_order_results,
        periodic_report_minutes=int(periodic_report_minutes),
        daily_review_time=daily_review_time,
    )
    if submitted:
        try:
            save_settings(new_settings)
        except Exception as exc:
            st.error(f"설정 저장 실패: {exc}")
        else:
            st.success("설정을 저장했습니다.")
            st.rerun()
    st.subheader("거래 성향이 바꾸는 기준")
    preview = [
        {
            "성향": TRADING_STYLES[key]["label"],
            "설명": TRADING_STYLES[key]["description"],
            "추천 점수 기준": f"{TradingSettings(**{**asdict(settings), 'trading_style': key}).effective_min_recommendation_score():.1f}",
            "거래대금 기준": f"{TradingSettings(**{**asdict(settings), 'trading_style': key}).effective_min_24h_trade_value_krw():,.0f} KRW",
            "허용 등락률": f"{TradingSettings(**{**asdict(settings), 'trading_style': key}).effective_max_change_rate_abs():.1%}",
            "거래량 기준": f"평균 x {TradingSettings(**{**asdict(settings), 'trading_style': key}).volume_multiplier():.2f}",
            "급등 차단": f"{TradingSettings(**{**asdict(settings), 'trading_style': key}).recent_surge_limit():.1%}",
        }
        for key in style_keys
    ]
    st.dataframe(pd.DataFrame(preview), use_container_width=True, hide_index=True)
    return new_settings


def render_coin_tab(config: Config, client: UpbitClient, settings: TradingSettings) -> None:
    st.subheader("코인 관리")
    st.info("업비트 KRW 마켓을 가져온 뒤 감시/추천/Telegram 승인/자동매매/제외 여부를 체크박스로 설정합니다.")
    if st.button("업비트 등록 코인 동기화", type="primary"):
        try:
            registry = sync_markets(get_krw_markets(client))
        except Exception as exc:
            st.error(f"동기화 실패: {exc}")
        else:
            st.success(f"{len(registry)}개 KRW 마켓을 동기화했습니다.")
            st.rerun()

    registry = load_registry()
    if not registry:
        st.warning("아직 코인 등록부가 없습니다. 먼저 동기화 버튼을 누르세요.")
        return

    group_filter = st.selectbox("그룹 필터", ["전체", *GROUP_POLICIES.keys()])
    search = st.text_input("코인 검색", placeholder="KRW-ETH 또는 이더리움")
    rows = []
    for entry in registry.values():
        if group_filter != "전체" and entry.group != group_filter:
            continue
        blob = f"{entry.market} {entry.korean_name} {entry.english_name}".lower()
        if search and search.lower() not in blob:
            continue
        rows.append(entry)
    rows = sorted(rows, key=lambda item: item.market)[:80]

    edited: dict[str, CoinEntry] = {}
    for entry in rows:
        with st.container(border=True):
            cols = st.columns([1.5, 1.5, 1.2, 1, 1, 1, 1, 1.6])
            cols[0].markdown(f"**{entry.market}**")
            cols[1].write(entry.korean_name or entry.english_name or "-")
            group = cols[2].selectbox("그룹", list(GROUP_POLICIES.keys()), index=list(GROUP_POLICIES.keys()).index(entry.group) if entry.group in GROUP_POLICIES else 2, key=f"group_{entry.market}")
            watch = cols[3].checkbox("감시", value=entry.watch, key=f"watch_{entry.market}")
            allow_recommend = cols[4].checkbox("추천", value=entry.allow_recommend, key=f"recommend_{entry.market}")
            allow_telegram_approval = cols[5].checkbox("승인", value=entry.allow_telegram_approval, key=f"approval_{entry.market}")
            allow_auto_trade = cols[6].checkbox("자동", value=entry.allow_auto_trade, key=f"auto_{entry.market}")
            excluded = cols[7].checkbox("제외", value=entry.excluded, key=f"excluded_{entry.market}")
            edited[entry.market] = CoinEntry(
                market=entry.market,
                korean_name=entry.korean_name,
                english_name=entry.english_name,
                group="excluded" if excluded else group,
                watch=False if excluded else watch,
                allow_recommend=False if excluded else allow_recommend,
                allow_telegram_approval=False if excluded else allow_telegram_approval,
                allow_auto_trade=False if excluded else allow_auto_trade,
                excluded=excluded,
                note=entry.note,
            )

    if st.button("코인 설정 저장", type="primary", use_container_width=True):
        registry.update(edited)
        save_registry(registry)
        st.success("코인 설정을 저장했습니다.")
        st.rerun()

    with st.expander("그룹 쉬운 설명", expanded=True):
        for name, desc in GROUP_POLICIES.items():
            st.write(f"- **{name}**: {desc}")


def render_recommendation_tab(config: Config, client: UpbitClient, settings: TradingSettings) -> None:
    st.subheader("시장상태 복합전략 / 추천 코인")
    st.warning("추천 갱신 버튼 자체는 주문을 보내지 않습니다. 완전 자동 운영에서는 워커가 별도로 검증한 추천만 주문합니다.")
    col1, col2 = st.columns(2)
    if col1.button("추천 갱신", type="primary", use_container_width=True):
        try:
            registry = sync_markets(get_krw_markets(client))
            candidates = scan_candidates(client, registry, settings)
            state = generate_recommendations(client, candidates, registry, settings)
        except Exception as exc:
            st.error(f"추천 갱신 실패: {exc}")
        else:
            st.success(f"추천 {len(state.recommendations)}개를 생성했습니다.")
            st.rerun()
    if col2.button("1위 추천 Telegram 승인 요청", use_container_width=True):
        state = load_recommendation_state()
        if not state.recommendations:
            st.warning("먼저 추천 갱신을 실행하세요.")
        else:
            ok, msg = send_telegram(config, format_recommendation_message(state.recommendations[0], rank=1, buy_amount_krw=settings.buy_amount_krw))
            st.success(msg) if ok else st.error(msg)

    state = load_recommendation_state()
    st.caption(f"마지막 추천 생성: {state.generated_at or '-'}")
    if state.market_regime:
        st.info(f"현재 시장상태: {state.market_regime} · {state.market_regime_reason}")
    if not state.recommendations:
        st.info("현재 시장상태에서 모든 필수 조건을 통과한 코인이 없습니다.")
        return

    rows = [
        {
            "순위": idx,
            "마켓": rec.market,
            "점수": rec.score,
            "현재가": rec.price,
            "등락률": f"{rec.change_rate:+.2%}",
            "24h 거래대금": f"{rec.trade_value_24h:,.0f}",
            "RSI": rec.rsi,
            "추세": rec.trend,
            "선택 전략": rec.strategy_label,
            "시장상태": rec.market_regime,
            "주문배수": f"{rec.position_size_ratio:.0%}",
            "예상 주문금액": f"{settings.buy_amount_krw * rec.position_size_ratio:,.0f}",
            "그룹": rec.group,
        }
        for idx, rec in enumerate(state.recommendations, start=1)
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    selected = st.selectbox("상세 확인 / 승인 대상", [rec.market for rec in state.recommendations])
    rec = next(item for item in state.recommendations if item.market == selected)
    st.text_area("Telegram에 전송될 추천/승인 메시지", value=format_recommendation_message(rec, rank=1, buy_amount_krw=settings.buy_amount_krw), height=360)
    confirm = st.text_input("대시보드 실제 승인 매수 확인 문구", placeholder=DASHBOARD_APPROVAL_TEXT)
    col1, col2 = st.columns(2)
    if col1.button("선택 코인 Telegram으로 묻기", use_container_width=True):
        ok, msg = send_telegram(config, format_recommendation_message(rec, rank=1, buy_amount_krw=settings.buy_amount_krw))
        st.success(msg) if ok else st.error(msg)
    if col2.button("대시보드에서 승인 매수 실행", type="primary", use_container_width=True, disabled=(confirm != DASHBOARD_APPROVAL_TEXT)):
        st.error("실제 주문 실행을 요청했습니다. 결과를 반드시 확인하세요.")
        result = approve_recommendation(config, selected)
        st.code(result, language="text")


def render_telegram_tab(config: Config, settings: TradingSettings) -> None:
    st.subheader("Telegram 명령어 / 의사결정 참여")
    st.info("사용자는 Telegram에서 추천 이유를 묻고, 승인/거절/제외/그룹 변경/운영 단계 변경을 할 수 있습니다.")

    st.subheader("알림 유형 / 순서 / 폭주 방지")
    st.warning("알림 폭주를 막기 위해 '워커 단계'와 '매매 신호'는 기본 OFF입니다. 꼭 필요한 유형만 켜세요.")
    rules = load_notification_rules()
    edited_rules: dict[str, NotificationRule] = {}
    with st.form("notification_rules_form"):
        st.caption("순서 숫자가 낮을수록 먼저 중요한 알림으로 취급합니다. 최소 간격 동안 같은 유형의 Telegram 알림은 다시 보내지 않습니다.")
        for rule in ordered_rules():
            with st.container(border=True):
                cols = st.columns([1.2, 1, 1, 1.5, 3])
                enabled = cols[0].checkbox(rule.label, value=rule.enabled, key=f"notify_enabled_{rule.key}")
                order = cols[1].number_input("순서", min_value=1, max_value=99, value=int(rule.order), key=f"notify_order_{rule.key}")
                minutes = max(0, int(rule.min_interval_seconds // 60))
                interval_minutes = cols[2].number_input("최소 간격(분)", min_value=0, max_value=1440, value=minutes, key=f"notify_interval_{rule.key}")
                cols[3].code(rule.key)
                cols[4].write(rule.description)
                edited_rules[rule.key] = NotificationRule(
                    key=rule.key,
                    label=rule.label,
                    enabled=enabled,
                    order=int(order),
                    min_interval_seconds=int(interval_minutes) * 60,
                    description=rule.description,
                )
        if st.form_submit_button("알림 설정 저장", type="primary", use_container_width=True):
            save_notification_rules(edited_rules)
            st.success("알림 설정을 저장했습니다.")
            st.rerun()

    st.subheader("추천 알림 조합 예시")
    st.markdown(
        """
- 조용한 운영: `승인 요청`, `주문 결과`, `위험/오류`, `일일 복기`만 ON
- 적극 모니터링: 조용한 운영 + `추천 갱신` ON
- 디버깅: `워커 단계` ON, 최소 간격 30분 이상 권장
- 폭주 위험: `워커 단계` 최소 간격 0분, `매매 신호` ON, HOLD 알림 ON 조합은 피하세요.
        """
    )

    st.dataframe(
        pd.DataFrame(
            [
                {"명령어": cmd.command, "목적": cmd.purpose, "예시": cmd.example, "효과": cmd.decision_effect}
                for cmd in TELEGRAM_COMMANDS
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
    st.subheader("알림 설정 현황")
    st.write(f"추천 알림: `{settings.notify_recommendations}`")
    st.write(f"승인 요청 알림: `{settings.notify_approval_requests}`")
    st.write(f"주문 결과 알림: `{settings.notify_order_results}`")
    st.write(f"주기 리포트: `{settings.periodic_report_minutes}`분")
    st.write(f"일일 복기 시간: `{settings.daily_review_time}`")
    if st.button("Telegram 테스트 메시지 전송"):
        ok, msg = send_telegram(config, "Telegram 연결 테스트입니다. 대시보드에서 전송했습니다.")
        st.success(msg) if ok else st.error(msg)


def render_manual_order_tab(config: Config, client: UpbitClient) -> None:
    st.subheader("수동 실제 주문")
    real_ready = config.real_trade_enabled and credentials_ready(config)
    if not real_ready:
        st.warning("수동 실제 주문은 DRY_RUN=false, ENABLE_REAL_TRADE=true, API 키 정상일 때만 활성화됩니다.")
    confirmation = st.text_input("실제 주문 확인 문구", placeholder=REAL_TRADE_CONFIRMATION)
    confirmed = confirmation == REAL_TRADE_CONFIRMATION
    try:
        registry = sync_markets(get_krw_markets(client))
        market_options = sorted(market for market, entry in registry.items() if market.startswith("KRW-") and not entry.excluded)
    except Exception:
        market_options = [config.market]
    if config.market not in market_options:
        market_options.insert(0, config.market)
    selected_market = st.selectbox(
        "주문 대상 마켓",
        market_options,
        index=market_options.index(config.market) if config.market in market_options else 0,
        help="수동 주문은 BTC 고정이 아니라 업비트 KRW 마켓 중 선택한 코인으로 실행됩니다.",
    )
    tab_buy, tab_sell, tab_strategy = st.tabs(["시장가 매수", "시장가 매도", "현재 전략 1회 실행"])
    with tab_buy:
        krw_amount = st.number_input("매수 금액 KRW", min_value=0, value=int(config.min_order_krw), step=1000)
        if st.button("실제 시장가 매수", disabled=not (real_ready and confirmed and krw_amount >= config.min_order_krw), type="primary"):
            st.json(client.market_buy(selected_market, float(krw_amount)))
    with tab_sell:
        volume = st.number_input("매도 수량", min_value=0.0, value=0.0, step=0.0001, format="%.8f")
        if st.button("실제 시장가 매도", disabled=not (real_ready and confirmed and volume > 0), type="primary"):
            st.json(client.market_sell(selected_market, float(volume)))
    with tab_strategy:
        st.caption(f"전략 1회 실행은 현재 전략 진단 마켓인 {config.market}에만 적용됩니다.")
        try:
            snapshot = fetch_snapshot(config, client)
            st.info(f"현재 신호: {korean_action(str(snapshot['signal'].get('action')))} / {korean_reason(str(snapshot['signal'].get('reason')))}")
            if st.button("현재 전략 신호 1회 실행", disabled=not confirmed):
                result = execute_strategy_once(config, client, snapshot)
                st.json(result or {"message": "실행된 주문이 없습니다."})
        except Exception as exc:
            st.error(exc)


def render_easy_words_tab() -> None:
    st.subheader("쉬운말 풀이")
    items = [
        ("운영 단계", "봇이 얼마나 스스로 행동할지 정하는 수준입니다. 1단계는 추천만, 2단계는 물어보고 매매입니다."),
        ("거래 성향", "보수적은 적게 사고 신중히 기다립니다. 균형은 기본값입니다. 적극적은 추천 기준과 진입 조건을 조금 낮춰 더 자주 기회를 찾습니다."),
        ("추천 점수", "거래대금, 추세, RSI, 거래량 등을 합쳐서 이 코인을 볼 만한지 숫자로 표현한 값입니다."),
        ("시장상태", "비트코인 1시간 흐름을 기준으로 지금 시장을 상승장, 횡보장, 중립장, 위험장으로 나눈 값입니다."),
        ("추세 눌림목", "큰 흐름은 오르지만 잠시 가격이 내려왔다가 다시 힘을 내는 구간에서 매수하는 방법입니다."),
        ("변동성 돌파", "최근 고점을 평소보다 큰 거래량으로 넘어설 때 상승이 시작됐다고 보고 진입하는 방법입니다."),
        ("평균회귀", "횡보장에서 가격이 평소 범위 아래로 내려갔다가 가운데로 돌아오는 움직임을 이용하는 방법입니다."),
        ("거래대금", "사람들이 실제로 사고판 돈의 크기입니다. 거래대금이 클수록 사고팔기 쉬운 편입니다."),
        ("RSI", "너무 많이 올랐는지, 너무 많이 떨어졌는지 보는 지표입니다."),
        ("손절률", "내가 정한 만큼 손실이 나면 더 큰 손실을 막기 위해 파는 기준입니다."),
        ("익절률", "내가 정한 만큼 수익이 나면 수익을 챙기기 위해 파는 기준입니다."),
        ("트레일링 스탑", "수익이 나다가 되밀릴 때 일부 수익을 지키려고 파는 기준입니다."),
        ("제외 코인", "내가 보기 싫거나 위험하다고 판단해서 추천과 매매에서 빼는 코인입니다."),
        ("그룹", "코인을 대형, 거래량 상위, 고위험, 제외처럼 묶어서 서로 다른 정책을 적용하는 기능입니다."),
        ("Telegram 승인", "봇이 바로 사지 않고 사용자에게 물어본 뒤, 사용자가 승인해야 매수하는 방식입니다."),
    ]
    for title, body in items:
        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.write(body)


def render_design_tab() -> None:
    st.subheader("시스템 설계 / 동작 방식")
    st.info(
        "1차 사상설계: 이 프로젝트는 비트코인 단일 자동매매가 아니라 업비트 KRW 마켓 전체 운용 시스템입니다. "
        "BTC는 별도 전략 진단 마켓으로 쓰일 수 있지만, 추천/보유/매수/매도 판단은 코인 관리 정책과 보유자산 전체를 기준으로 동작합니다."
    )
    st.markdown(
        """
운용 구조:
- 전체 자산 현황: 업비트 계좌의 KRW와 모든 보유 코인을 KRW로 환산해 표시합니다.
- 추천 대상: 업비트 KRW 마켓 전체에서 제외/감시/그룹/자동매매 체크박스 정책을 통과한 코인을 스캔합니다.
- 시장상태: BTC 1시간봉의 EMA20·EMA60·EMA200, ADX, ATR로 상승장·횡보장·중립장·위험장을 구분합니다.
- 전략 선택: 상승장은 다중 조건 추세·눌림목·변동성 돌파, 횡보장은 평균회귀, 위험장은 신규매수 중단을 적용합니다.
- 자동매수: 선택 전략, 추천 점수, 운영 단계, 자동매매 허용, 코인당 한도, 현금과 손실 제한을 모두 통과한 코인만 한 번 주문합니다.
- 자동매도: 공통 손절·익절·추적매도와 함께 돌파 60분, 평균회귀 120분 보유시간 규칙을 점검합니다.
- 전략 진단 마켓: `.env`의 MARKET 값은 별도 이동평균 전략 진단과 1회 실행에만 사용됩니다.
        """
    )
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "단계": f"{mode.level}단계",
                    "이름": mode.name,
                    "의사결정": mode.decision_policy,
                    "매매 정책": mode.trade_policy,
                }
                for mode in OPERATION_MODES
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )
    st.subheader("승인형 실제 추천 매매 흐름")
    st.dataframe(pd.DataFrame([{"순서": title, "설명": desc} for title, desc in APPROVAL_FLOW]), use_container_width=True, hide_index=True)
    st.graphviz_chart(
        """
digraph {
  graph [rankdir=LR, bgcolor="transparent"];
  node [shape=box, style="rounded,filled", fillcolor="#F7F7F7", color="#666666", fontname="Malgun Gothic"];
  edge [color="#777777", fontname="Malgun Gothic"];
  Scan [label="업비트 등록 코인 스캔"];
  Filter [label="제외/그룹/체크박스 필터"];
  Regime [label="BTC 시장상태 판정"];
  Score [label="전략 선택/추천 점수"];
  Ask [label="Telegram으로 물어보기"];
  Why [label="/why로 사유 질문"];
  Approve [label="/approve 또는 대시보드 승인"];
  Risk [label="금액/손실/포지션 재검증"];
  Order [label="실제 주문"];
  Record [label="이력 저장/복기"];
  Scan -> Filter -> Regime -> Score -> Ask -> Approve -> Risk -> Order -> Record;
  Ask -> Why -> Approve;
}
        """,
        use_container_width=True,
    )
    st.subheader("탭별 기능 설명")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "탭": tab.tab_name,
                    "목적": tab.purpose,
                    "주요 컨트롤": ", ".join(tab.main_controls),
                    "쉬운 설명": tab.beginner_explanation,
                }
                for tab in DASHBOARD_TABS
            ]
        ),
        use_container_width=True,
        hide_index=True,
    )


def render_logs_tab() -> None:
    st.subheader("거래 이력")
    history_path = PROJECT_DIR / "trade_history.jsonl"
    history = load_trade_history()
    if history.empty:
        st.info("아직 표시할 거래/추천 이력이 없습니다.")
    else:
        trade_rows = history[history["유형"].isin(["auto_buy", "auto_sell", "approve_buy", "strategy_order", "order_fill_check"])]
        blocked_rows = history[history["유형"].str.contains("blocked", na=False)]
        refresh_rows = history[history["유형"].eq("recommendation_refresh")]

        cols = st.columns(4)
        cols[0].metric("전체 이력", f"{len(history):,}건")
        cols[1].metric("매수/체결 이력", f"{len(trade_rows):,}건")
        cols[2].metric("보류/차단 이력", f"{len(blocked_rows):,}건")
        cols[3].metric("추천 갱신", f"{len(refresh_rows):,}건")

        tab_orders, tab_blocked, tab_all, tab_raw = st.tabs(["매수/체결", "보류/차단", "전체 이력", "원문"])
        with tab_orders:
            if trade_rows.empty:
                st.info("매수/체결 이력이 없습니다.")
            else:
                st.dataframe(trade_rows, use_container_width=True, hide_index=True)
        with tab_blocked:
            if blocked_rows.empty:
                st.info("보류/차단 이력이 없습니다.")
            else:
                st.dataframe(blocked_rows, use_container_width=True, hide_index=True)
        with tab_all:
            st.dataframe(history, use_container_width=True, hide_index=True)
        with tab_raw:
            if history_path.exists():
                st.code("\n".join(history_path.read_text(encoding="utf-8", errors="replace").splitlines()[-120:]), language="json")

    st.subheader("시스템 로그")
    st.code(read_logs(), language="text")


def render_parameter_strip(config: Config, settings: TradingSettings) -> None:
    trade_mode = "실거래" if config.real_trade_enabled else "모의거래"
    approval = "승인 필수" if settings.approval_required else "자동 판단"
    items = [
        ("운영 단계", settings.mode_label),
        ("거래 성향", settings.style_label),
        ("주문 모드", trade_mode),
        ("복합전략", "시장상태 자동선택"),
        ("진입 권한", approval),
        ("1회 매수", f"{settings.buy_amount_krw:,.0f}원"),
        ("자동매수 슬롯", f"{settings.max_positions}개"),
        ("손절 / 익절", f"-{settings.stop_loss_rate:.1%} / +{settings.take_profit_rate_1:.1%}, +{settings.take_profit_rate_2:.1%}"),
        ("유효 추천점수", f"{settings.effective_min_recommendation_score():.0f}점 이상"),
    ]
    html = "".join(
        f'<div class="parameter-item"><div class="parameter-label">{label}</div>'
        f'<div class="parameter-value">{value}</div></div>'
        for label, value in items
    )
    st.markdown(f'<div class="parameter-strip">{html}</div>', unsafe_allow_html=True)


def render_sidebar(config: Config, settings: TradingSettings) -> tuple[str, bool, int]:
    state = load_state()
    with st.sidebar:
        st.header("기능")
        page = st.radio(
            "이동",
            [
                "전체 자산",
                "보유 코인",
                "추천 코인",
                "운영 및 파라미터",
                "코인 관리",
                "Telegram 알림",
                "거래 이력 및 로그",
                "전략 진단",
                "수동 주문",
                "쉬운말 풀이",
                "설계 및 구조",
            ],
            label_visibility="collapsed",
        )

        st.divider()
        st.subheader("운영 제어")
        running_state = "킬 스위치" if state.kill_switch else ("일시정지" if state.paused else "실행 중")
        status_badge("현재 상태", running_state, "danger" if state.kill_switch else "warn" if not state.paused else "safe")
        start_col, pause_col = st.columns(2)
        if start_col.button("실행 / 재개", type="primary", help="실거래가 켜져 있으면 자동 주문 판단도 재개됩니다."):
            set_command("resume", "dashboard_sidebar")
            st.rerun()
        if pause_col.button("일시정지", help="신규 판단과 주문을 일시정지합니다."):
            set_command("pause", "dashboard_sidebar")
            st.rerun()
        kill_col, reset_col = st.columns(2)
        if kill_col.button("긴급정지", help="신규 주문을 즉시 차단합니다."):
            set_command("kill", "dashboard_sidebar")
            st.rerun()
        if reset_col.button("정지 해제", help="킬 스위치를 해제하되 일시정지는 유지합니다."):
            set_command("reset", "dashboard_sidebar")
            st.rerun()

        st.divider()
        st.subheader("연결 상태")
        st.write("운용 범위: `업비트 KRW 마켓 전체`")
        st.write(f"전략 진단: `{config.market}`")
        st.write(f"API 키: `{'설정됨' if credentials_ready(config) else '미설정'}`")
        st.write(f"워커 갱신: `{state.last_heartbeat or '-'}`")

        st.divider()
        auto_refresh = st.checkbox("실시간 자동 새로고침", value=True)
        refresh_seconds = st.number_input("새로고침 주기(초)", min_value=3, max_value=60, value=5, step=1)
        if st.button("지금 새로고침"):
            st.rerun()
    return page, auto_refresh, int(refresh_seconds)


def main() -> None:
    config = load_config()
    settings = load_settings()
    client = make_client(config)

    if "paper_krw" not in st.session_state:
        st.session_state.paper_krw = config.paper_initial_krw
    if "position" not in st.session_state:
        st.session_state.position = Position(config.market, config.base_currency)

    page, auto_refresh, refresh_seconds = render_sidebar(config, settings)

    st.title("Orage Bot  대시보드 ")
    st.caption("업비트 KRW 마켓 전체 보유자산과 추천·매수·매도 상태를 통합 운영합니다.")
    render_parameter_strip(config, settings)

    def render_selected_page() -> None:
        if page == "전체 자산":
            render_live_tab(config, client)
        elif page == "보유 코인":
            render_holdings_tab(config, client, settings)
        elif page == "추천 코인":
            render_recommendation_tab(config, client, settings)
        elif page == "운영 및 파라미터":
            render_settings_tab(settings)
        elif page == "코인 관리":
            render_coin_tab(config, client, settings)
        elif page == "Telegram 알림":
            render_telegram_tab(config, settings)
        elif page == "거래 이력 및 로그":
            render_logs_tab()
        elif page == "전략 진단":
            render_strategy_diagnostics_tab(config, client)
        elif page == "수동 주문":
            render_manual_order_tab(config, client)
        elif page == "쉬운말 풀이":
            render_easy_words_tab()
        elif page == "설계 및 구조":
            render_design_tab()

    live_pages = {"전체 자산", "보유 코인", "추천 코인", "거래 이력 및 로그", "전략 진단"}
    if auto_refresh and page in live_pages:
        @st.fragment(run_every=float(refresh_seconds))
        def render_live_page() -> None:
            render_selected_page()

        render_live_page()
    else:
        render_selected_page()


if __name__ == "__main__":
    main()

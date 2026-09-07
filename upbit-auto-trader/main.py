from __future__ import annotations

import time
import json
from dataclasses import asdict
from datetime import datetime, timedelta
from pathlib import Path

from coin_registry import CoinEntry, load_registry, sync_markets
from config import Config
from indicators import add_indicators
from logger import setup_logger
from market_scanner import get_krw_markets, scan_candidates
from notifier import StepNotifier, korean_action, korean_reason
from recommendation_engine import format_recommendation_message, generate_recommendations
from recommendation_state import HISTORY_PATH, Recommendation, append_history
from risk_manager import RiskManager
from runtime_state import load_state, set_command, update_market_status, update_state
from settings_store import load_settings
from strategy import MovingAverageStrategy, Position
from trader import Trader
from upbit_client import UpbitClient


def _today_auto_trade_count() -> int:
    if not HISTORY_PATH.exists():
        return 0
    today = datetime.now().strftime("%Y-%m-%d")
    count = 0
    for line in HISTORY_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        final_result = row.get("final_result") or row.get("result") or {}
        executed_volume = float(final_result.get("executed_volume", 0) or 0)
        if (
            str(row.get("time", "")).startswith(today)
            and row.get("event") in {"auto_buy", "approve_buy"}
            and (executed_volume > 0 or final_result.get("dry_run"))
        ):
            count += 1
    return count


def _recent_auto_buy_exists(market: str, minutes: int = 30) -> bool:
    if not HISTORY_PATH.exists():
        return False
    cutoff = datetime.now() - timedelta(minutes=minutes)
    for line in HISTORY_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            traded_at = datetime.strptime(str(row.get("time", "")), "%Y-%m-%d %H:%M:%S")
        except (json.JSONDecodeError, ValueError):
            continue
        if row.get("event") == "auto_buy" and row.get("market") == market and traded_at >= cutoff:
            return True
    return False


def _trade_cooldown_reason(market: str, settings) -> str:
    if not HISTORY_PATH.exists():
        return ""
    now = datetime.now()
    for line in reversed(HISTORY_PATH.read_text(encoding="utf-8", errors="replace").splitlines()):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            traded_at = datetime.strptime(str(row.get("time", "")), "%Y-%m-%d %H:%M:%S")
        except (json.JSONDecodeError, ValueError):
            continue
        if row.get("event") != "auto_sell" or row.get("market") != market:
            continue
        profit_rate = float(row.get("profit_rate", 0) or 0)
        cooldown = settings.loss_cooldown_minutes if profit_rate <= 0 else settings.profit_cooldown_minutes
        elapsed_minutes = (now - traded_at).total_seconds() / 60
        if elapsed_minutes < cooldown:
            label = "손실" if profit_rate <= 0 else "수익"
            return f"최근 {label} 매도 후 재진입 대기 중 ({elapsed_minutes:.0f}/{cooldown}분)"
        return ""
    return ""


def _loss_streak_pause_reason(settings) -> str:
    if not HISTORY_PATH.exists():
        return ""
    losses: list[datetime] = []
    for line in reversed(HISTORY_PATH.read_text(encoding="utf-8", errors="replace").splitlines()):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if row.get("event") != "auto_sell":
                continue
            traded_at = datetime.strptime(str(row.get("time", "")), "%Y-%m-%d %H:%M:%S")
            profit_rate = float(row.get("profit_rate", 0) or 0)
        except (json.JSONDecodeError, ValueError, TypeError):
            continue
        if profit_rate > 0:
            break
        losses.append(traded_at)
        if len(losses) >= settings.max_consecutive_losses:
            elapsed_minutes = (datetime.now() - losses[0]).total_seconds() / 60
            if elapsed_minutes < settings.loss_pause_minutes:
                return (
                    f"연속 {settings.max_consecutive_losses}회 손실로 신규매수 일시정지 "
                    f"({elapsed_minutes:.0f}/{settings.loss_pause_minutes}분)"
                )
            break
    return ""


def _active_auto_position_count(
    client: UpbitClient,
    registry: dict[str, CoinEntry],
    min_position_krw: float,
) -> tuple[int, set[str]]:
    accounts = client.get_accounts()
    amounts: dict[str, float] = {}
    for account in accounts:
        currency = str(account.get("currency", ""))
        if not currency or currency == "KRW":
            continue
        market = f"KRW-{currency}"
        entry = registry.get(market)
        if not entry or entry.excluded or not entry.allow_auto_trade:
            continue
        amount = float(account.get("balance", 0) or 0) + float(account.get("locked", 0) or 0)
        if amount > 0:
            amounts[market] = amount

    active: set[str] = set()
    markets = sorted(amounts)
    for index in range(0, len(markets), 80):
        batch = markets[index : index + 80]
        if not batch:
            continue
        tickers = client._request("GET", "/v1/ticker", {"markets": ",".join(batch)})
        for ticker in tickers:
            market = str(ticker.get("market", ""))
            value = amounts.get(market, 0.0) * float(ticker.get("trade_price", 0) or 0)
            if value >= min_position_krw:
                active.add(market)
    return len(active), active


def _execution_status(result: dict) -> str:
    executed_volume = float(result.get("executed_volume", 0) or 0)
    if executed_volume > 0:
        return "filled"
    if result.get("state") in {"cancel", "done"}:
        return "not_filled"
    return "pending"


def _latest_entry_strategy(market: str) -> tuple[str, datetime | None]:
    if not HISTORY_PATH.exists():
        return "", None
    for line in reversed(HISTORY_PATH.read_text(encoding="utf-8", errors="replace").splitlines()):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            if row.get("event") != "auto_buy" or row.get("market") != market:
                continue
            traded_at = datetime.strptime(str(row.get("time", "")), "%Y-%m-%d %H:%M:%S")
        except (json.JSONDecodeError, ValueError):
            continue
        recommendation = row.get("recommendation") or {}
        return str(recommendation.get("strategy_name", "")), traded_at
    return "", None


def _daily_loss_block_reason(total_equity: float, settings) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    baseline = 0.0
    if HISTORY_PATH.exists():
        for line in HISTORY_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("event") == "daily_equity_baseline" and str(row.get("time", "")).startswith(today):
                baseline = float(row.get("total_equity", 0) or 0)
                break
    if baseline <= 0:
        append_history("daily_equity_baseline", {"total_equity": total_equity})
        return ""
    loss_rate = max(0.0, (baseline - total_equity) / baseline)
    if loss_rate >= settings.max_daily_loss_rate:
        return f"하루 계좌 손실 제한 도달 ({loss_rate:.2%}/{settings.max_daily_loss_rate:.2%})"
    return ""


def auto_buy_recommendation(
    *,
    config: Config,
    client: UpbitClient,
    settings,
    recommendation: Recommendation,
    registry: dict[str, CoinEntry],
    notifier: StepNotifier,
) -> dict | None:
    market = recommendation.market
    entry = registry.get(market, CoinEntry(market=market))
    if entry.excluded or not entry.watch or not entry.allow_recommend:
        append_history("auto_buy_blocked", {"market": market, "reason": "감시/추천 허용 대상이 아님"})
        return None
    if not entry.allow_auto_trade:
        append_history("auto_buy_blocked", {"market": market, "reason": "자동매매 허용 체크가 꺼져 있음"})
        return None
    if _today_auto_trade_count() >= settings.max_daily_trades:
        append_history("auto_buy_blocked", {"market": market, "reason": "하루 최대 거래 횟수 초과"})
        return None
    if _recent_auto_buy_exists(market):
        append_history("auto_buy_blocked", {"market": market, "reason": "같은 코인 30분 내 반복 자동매수 차단"})
        return None
    cooldown_reason = _trade_cooldown_reason(market, settings)
    if cooldown_reason:
        append_history("auto_buy_blocked", {"market": market, "reason": cooldown_reason})
        return None
    loss_pause_reason = _loss_streak_pause_reason(settings)
    if loss_pause_reason:
        append_history("auto_buy_blocked", {"market": market, "reason": loss_pause_reason})
        return None
    if not config.real_trade_enabled:
        append_history("auto_buy_blocked", {"market": market, "reason": "실거래 설정이 꺼져 있음"})
        return None

    base_currency = market.split("-")[1]
    balance = client.get_balance(base_currency)
    position_volume = float(balance.get("balance", 0.0)) + float(balance.get("locked", 0.0))
    position_value = position_volume * float(recommendation.price)
    remaining_coin_limit = max(0.0, settings.per_coin_max_krw - position_value)
    active_count, active_markets = _active_auto_position_count(client, registry, config.min_order_krw)
    if active_count > settings.max_positions or (market not in active_markets and active_count >= settings.max_positions):
        append_history(
            "auto_buy_blocked",
            {
                "market": market,
                "reason": "자동매매 최대 보유 종목 수 도달",
                "active_positions": active_count,
                "max_positions": settings.max_positions,
            },
        )
        return None

    total_equity, available_krw, _ = fetch_total_portfolio_value(client)
    daily_loss_reason = _daily_loss_block_reason(total_equity, settings)
    if daily_loss_reason:
        append_history("auto_buy_blocked", {"market": market, "reason": daily_loss_reason})
        return None
    reserve_krw = max(settings.min_cash_reserve_krw, total_equity * settings.min_cash_reserve_ratio)
    spendable_krw = max(0.0, available_krw - reserve_krw)
    strategy_order_krw = settings.buy_amount_krw * max(0.0, min(recommendation.position_size_ratio, 1.0))
    order_krw = min(strategy_order_krw, remaining_coin_limit, spendable_krw)

    if order_krw < config.min_order_krw:
        append_history(
            "auto_buy_blocked",
            {
                "market": market,
                "reason": "주문 가능 금액이 최소 주문 금액보다 작음",
                "order_krw": order_krw,
                "position_value": position_value,
                "available_krw": available_krw,
                "required_cash_reserve_krw": reserve_krw,
                "strategy": recommendation.strategy_label,
            },
        )
        return None

    result = client.market_buy(market, order_krw)
    final_result = result
    uuid_value = str(result.get("uuid", ""))
    if uuid_value:
        time.sleep(1)
        try:
            final_result = client.get_order(uuid_value)
        except Exception:
            final_result = result
    append_history(
        "auto_buy",
        {
            "market": market,
            "order_krw": order_krw,
            "recommendation": asdict(recommendation),
            "result": result,
            "final_result": final_result,
            "execution_status": _execution_status(final_result),
            "operation_mode": settings.operation_mode,
            "trading_style": settings.trading_style,
        },
    )
    update_state(last_order_action="BUY", last_order_result=str(final_result), last_market=market)
    if settings.notify_order_results:
        notifier.telegram(
            (
                "[완전 자동 매매 체결 요청]\n"
                f"코인: {market}\n"
                f"금액: {order_krw:,.0f} KRW\n"
                f"추천 점수: {recommendation.score:.1f}/100\n"
                f"시장 상태: {recommendation.market_regime}\n"
                f"선택 전략: {recommendation.strategy_label}\n"
                f"성향: {settings.style_label}\n"
                f"주문 상태: {_execution_status(final_result)} ({final_result.get('state', '-')})\n"
                f"체결 수량: {final_result.get('executed_volume', '-')}\n"
                f"수수료: {final_result.get('paid_fee', '-')}\n"
                f"결과: {final_result}"
            ),
            rule_key="order_result",
        )
    return final_result


def _position_exit_signal(
    *,
    position: Position,
    current_price: float,
    settings,
    config: Config,
) -> dict[str, float | str] | None:
    profit_rate = position.profit_rate(current_price)
    position.highest_profit_rate = max(position.highest_profit_rate, profit_rate)
    trailing_drop = position.highest_profit_rate - profit_rate
    entry_strategy, entered_at = _latest_entry_strategy(position.market)
    holding_minutes = (datetime.now() - entered_at).total_seconds() / 60 if entered_at else 0.0

    if entry_strategy == "volatility_breakout" and holding_minutes >= 60 and profit_rate < 0.01:
        return {"action": "SELL", "sell_ratio": 1.0, "reason": f"돌파 전략 시간 종료: {holding_minutes:.0f}분 내 상승 부족"}
    if entry_strategy == "mean_reversion":
        if profit_rate >= 0.02:
            return {"action": "SELL", "sell_ratio": 1.0, "reason": f"평균회귀 목표 도달: {profit_rate:+.2%}"}
        if holding_minutes >= 120:
            return {"action": "SELL", "sell_ratio": 1.0, "reason": f"평균회귀 보유시간 종료: {holding_minutes:.0f}분"}

    if profit_rate <= -settings.stop_loss_rate:
        return {"action": "SELL", "sell_ratio": 1.0, "reason": f"손절 조건 도달: {profit_rate:+.2%}"}
    if profit_rate >= settings.take_profit_rate_2:
        return {"action": "SELL", "sell_ratio": 1.0, "reason": f"2차 익절 조건 도달: {profit_rate:+.2%}"}
    if profit_rate >= settings.take_profit_rate_1 and not position.first_profit_taken:
        return {
            "action": "SELL",
            "sell_ratio": config.take_profit_sell_ratio_1,
            "reason": f"1차 익절 조건 도달: {profit_rate:+.2%}",
        }
    if position.highest_profit_rate >= settings.trailing_activation_rate and trailing_drop >= settings.trailing_stop_rate:
        return {"action": "SELL", "sell_ratio": 1.0, "reason": f"트레일링 스탑 작동: 고점 대비 {trailing_drop:.2%} 하락"}
    return None


def monitor_altcoin_exits(
    *,
    config: Config,
    client: UpbitClient,
    settings,
    registry: dict[str, CoinEntry],
    positions: dict[str, Position],
    notifier: StepNotifier,
) -> list[dict]:
    if config.dry_run or not config.real_trade_enabled:
        return []
    if settings.operation_mode < 3:
        return []
    if settings.approval_required:
        return []

    results: list[dict] = []
    accounts = client.get_accounts()
    for account in accounts:
        currency = str(account.get("currency", ""))
        if not currency or currency == "KRW":
            continue

        market = f"KRW-{currency}"
        if market == config.market:
            continue

        entry = registry.get(market, CoinEntry(market=market))
        if entry.excluded or not entry.watch or not entry.allow_auto_trade:
            continue

        volume = float(account.get("balance", 0) or 0)
        locked = float(account.get("locked", 0) or 0)
        avg_buy_price = float(account.get("avg_buy_price", 0) or 0)
        if volume <= 0 or avg_buy_price <= 0:
            positions.pop(market, None)
            continue

        current_price = client.get_current_price(market)
        position_value = volume * current_price
        if position_value < config.min_order_krw:
            continue

        position = positions.get(market) or Position(market=market, currency=currency)
        position.market = market
        position.currency = currency
        position.volume = volume + locked
        position.avg_buy_price = avg_buy_price
        if position.buy_count == 0:
            position.buy_count = 1
        positions[market] = position

        signal = _position_exit_signal(position=position, current_price=current_price, settings=settings, config=config)
        if not signal:
            continue

        sell_ratio = min(max(float(signal["sell_ratio"]), 0.0), 1.0)
        sell_volume = volume * sell_ratio
        sell_value = sell_volume * current_price
        if sell_ratio < 1.0 and sell_value < config.min_order_krw:
            append_history(
                "auto_sell_blocked",
                {
                    "market": market,
                    "reason": "부분 매도 금액이 최소 주문 금액보다 작음",
                    "sell_value": sell_value,
                    "profit_rate": position.profit_rate(current_price),
                },
            )
            continue

        notifier.step("보유 코인 자동매도", f"{market} {signal['reason']}", rule_key="order_result")
        result = client.market_sell(market, sell_volume)
        final_result = result
        uuid_value = str(result.get("uuid", ""))
        if uuid_value:
            time.sleep(1)
            try:
                final_result = client.get_order(uuid_value)
            except Exception:
                final_result = result

        if sell_ratio >= 1.0:
            positions.pop(market, None)
        else:
            position.volume = max(0.0, position.volume - sell_volume)
            position.first_profit_taken = True

        payload = {
            "market": market,
            "sell_ratio": sell_ratio,
            "sell_volume": sell_volume,
            "price": current_price,
            "estimated_value_krw": sell_value,
            "profit_rate": position.profit_rate(current_price),
            "reason": str(signal["reason"]),
            "entry_strategy": _latest_entry_strategy(market)[0],
            "result": result,
            "final_result": final_result,
            "execution_status": _execution_status(final_result),
            "operation_mode": settings.operation_mode,
            "trading_style": settings.trading_style,
        }
        append_history("auto_sell", payload)
        update_state(last_order_action="SELL", last_order_result=str(final_result), last_market=market)
        results.append(payload)

        if settings.notify_order_results:
            notifier.telegram(
                (
                    "[보유 코인 자동매도]\n"
                    f"코인: {market}\n"
                    f"사유: {signal['reason']}\n"
                    f"매도 비율: {sell_ratio:.0%}\n"
                    f"예상 금액: {sell_value:,.0f} KRW\n"
                    f"현재가: {current_price:,.4f} KRW\n"
                    f"최종 상태: {final_result.get('state', '-')}\n"
                    f"체결 수량: {final_result.get('executed_volume', '-')}\n"
                    f"결과: {final_result}"
                ),
                rule_key="order_result",
            )

    return results


def fetch_total_portfolio_value(client: UpbitClient) -> tuple[float, float, int]:
    accounts = client.get_accounts()
    total_value = 0.0
    available_krw = 0.0
    markets: list[str] = []
    coin_amounts: dict[str, float] = {}

    for account in accounts:
        currency = str(account.get("currency", ""))
        balance = float(account.get("balance", 0) or 0)
        locked = float(account.get("locked", 0) or 0)
        amount = balance + locked
        if amount <= 0:
            continue
        if currency == "KRW":
            available_krw = balance
            total_value += amount
            continue
        market = f"KRW-{currency}"
        markets.append(market)
        coin_amounts[market] = amount

    if markets:
        try:
            valid_markets = {
                str(item.get("market", ""))
                for item in client._request("GET", "/v1/market/all", {"isDetails": "false"})
                if str(item.get("market", "")).startswith("KRW-")
            }
            query_markets = sorted(set(markets) & valid_markets)
            for index in range(0, len(query_markets), 80):
                batch = query_markets[index : index + 80]
                tickers = client._request("GET", "/v1/ticker", {"markets": ",".join(batch)})
                for item in tickers:
                    market = str(item.get("market", ""))
                    price = float(item.get("trade_price", 0) or 0)
                    total_value += coin_amounts.get(market, 0.0) * price
        except Exception:
            pass

    return total_value, available_krw, len([market for market, amount in coin_amounts.items() if amount > 0])


def build_position(config: Config, client: UpbitClient, fallback: Position | None = None) -> Position:
    if config.dry_run:
        return fallback or Position(market=config.market, currency=config.base_currency)

    balance = client.get_balance(config.base_currency)
    position = fallback or Position(market=config.market, currency=config.base_currency)
    position.market = config.market
    position.currency = config.base_currency
    position.volume = balance["balance"] + balance["locked"]
    position.avg_buy_price = balance["avg_buy_price"]

    if position.has_position and position.buy_count == 0:
        position.buy_count = 1
    if not position.has_position:
        position.buy_count = 0
        position.first_profit_taken = False
        position.highest_profit_rate = 0.0
    return position


def print_status(
    config: Config,
    current_price: float,
    position: Position,
    market_data,
    signal: dict,
) -> None:
    latest = market_data.iloc[-1]
    pnl = position.profit_rate(current_price)
    print("=" * 50)
    print(f"운용 범위: 업비트 KRW 마켓 전체")
    print(f"기준전략 마켓: {config.market}")
    print(f"현재가: {current_price:,.0f} KRW")
    print(f"보유수량: {position.volume:.8f} {config.base_currency}")
    print(f"평균매수가: {position.avg_buy_price:,.0f} KRW")
    print(f"손익률: {pnl:+.2%}")
    print(f"MA{config.ma_short}: {latest['ma_short']:,.0f}")
    print(f"MA{config.ma_mid}: {latest['ma_mid']:,.0f}")
    print(f"MA{config.ma_long}: {latest['ma_long']:,.0f}")
    print(f"RSI: {latest['rsi']:.1f}")
    print(f"신호: {korean_action(str(signal.get('action')))}")
    print(f"사유: {korean_reason(str(signal.get('reason')))}")
    print(f"모의거래: {config.dry_run}")
    print("=" * 50)


def main() -> None:
    project_dir = Path(__file__).resolve().parent
    config = Config.load(project_dir / ".env")
    logger = setup_logger(log_dir=str(project_dir / "logs"))
    notifier = StepNotifier(config, logger)

    client = UpbitClient(config.access_key, config.secret_key, config.base_url)
    risk_manager = RiskManager(config)
    trader = Trader(config, client, risk_manager, logger)
    position = Position(market=config.market, currency=config.base_currency)
    managed_positions: dict[str, Position] = {}
    paper_krw = config.paper_initial_krw
    last_recommendation_at = 0.0

    logger.info(
        "Starting Upbit portfolio auto trader. Scope=ALL_KRW_MARKETS StrategyMarket=%s DRY_RUN=%s RealTrade=%s",
        config.market,
        config.dry_run,
        config.enable_real_trade,
    )
    logger.warning("This program is for education and personal testing. It does not guarantee profit.")
    notifier.step(
        "봇 준비 완료",
        f"운용범위=업비트 KRW 마켓 전체, 전략진단={config.market}, 캔들={config.interval}, 모의거래={config.dry_run}, 실거래={config.real_trade_enabled}",
    )
    previous_control = load_state()
    update_state(
        paused=previous_control.paused,
        kill_switch=previous_control.kill_switch,
        last_status="paused" if previous_control.paused else "running",
        operating_scope="업비트 KRW 마켓 전체",
        strategy_market=config.market,
        dry_run=config.dry_run,
        real_trade_enabled=config.real_trade_enabled,
    )
    if not config.dry_run:
        try:
            startup_equity, _, _ = fetch_total_portfolio_value(client)
            _daily_loss_block_reason(startup_equity, load_settings())
        except Exception as exc:
            logger.warning("Daily equity baseline could not be initialized: %s", exc)

    while True:
        try:
            notifier.step("제어 상태 확인", "대시보드와 텔레그램 명령을 확인합니다.", telegram=False)
            control = load_state()
            if control.kill_switch:
                notifier.step("킬 스위치 작동 중", "자동매매 루프가 차단되었습니다.", rule_key="risk_alert")
                update_state(last_heartbeat=time.strftime("%Y-%m-%d %H:%M:%S"), last_status="kill switch active")
                time.sleep(config.loop_interval)
                continue
            if control.paused:
                notifier.step("일시정지 상태", "대시보드 또는 텔레그램에서 시작할 수 있습니다.", telegram=False)
                update_state(last_heartbeat=time.strftime("%Y-%m-%d %H:%M:%S"), last_status="paused")
                time.sleep(config.loop_interval)
                continue

            notifier.step("API 상태 확인", "업비트 공개 API 연결을 확인합니다.")
            api_ok = client.health_check()
            risk_manager.set_api_available(api_ok)
            if not api_ok:
                notifier.step("API 상태 이상", "이번 주기의 주문을 차단합니다.", rule_key="risk_alert")
                time.sleep(config.loop_interval)
                continue

            settings = load_settings()
            registry = load_registry()
            now = time.time()
            recommendation_interval = max(300, settings.periodic_report_minutes * 60)
            if settings.recommendation_enabled and now - last_recommendation_at >= recommendation_interval:
                notifier.step("추천 코인 갱신", "설정된 코인 그룹과 제외 목록을 기준으로 추천을 계산합니다.", rule_key="recommendation")
                try:
                    registry = sync_markets(get_krw_markets(client))
                    candidates = scan_candidates(client, registry, settings)
                    recommendation_state = generate_recommendations(client, candidates, registry, settings)
                    last_recommendation_at = now
                    append_history(
                        "recommendation_refresh",
                        {
                            "count": len(recommendation_state.recommendations),
                            "top_market": recommendation_state.recommendations[0].market if recommendation_state.recommendations else "",
                            "operation_mode": settings.operation_mode,
                            "trading_style": settings.trading_style,
                            "market_regime": recommendation_state.market_regime,
                            "market_regime_reason": recommendation_state.market_regime_reason,
                        },
                    )
                except Exception as exc:
                    notifier.step("추천 갱신 실패", str(exc), rule_key="risk_alert")
                    time.sleep(config.loop_interval)
                    continue

                if recommendation_state.recommendations and settings.operation_mode >= 4 and not settings.approval_required:
                    top = recommendation_state.recommendations[0]
                    notifier.step("완전 자동 추천 매매", f"{top.market} 자동 주문 조건을 확인합니다.", rule_key="order_result")
                    try:
                        auto_result = auto_buy_recommendation(
                            config=config,
                            client=client,
                            settings=settings,
                            recommendation=top,
                            registry=registry,
                            notifier=notifier,
                        )
                    except Exception as exc:
                        append_history(
                            "auto_buy_failed",
                            {
                                "market": top.market,
                                "score": round(top.score, 2),
                                "reason": str(exc),
                                "buy_amount_krw": settings.buy_amount_krw,
                                "operation_mode": settings.operation_mode,
                                "trading_style": settings.trading_style,
                            },
                        )
                        notifier.step("완전 자동 주문 실패", str(exc), rule_key="risk_alert")
                    else:
                        if auto_result:
                            notifier.step("완전 자동 주문 결과", str(auto_result), rule_key="order_result")
                        else:
                            notifier.step("완전 자동 주문 보류", f"{top.market} 자동 주문 조건을 통과하지 못했습니다.", rule_key="risk_alert")
                elif recommendation_state.recommendations and settings.notify_approval_requests and settings.operation_mode >= 2:
                    top = recommendation_state.recommendations[0]
                    notifier.step("추천 승인 요청", top.market, rule_key="approval_request")
                    append_history(
                        "approval_request",
                        {
                            "market": top.market,
                            "score": top.score,
                            "buy_amount_krw": settings.buy_amount_krw,
                            "operation_mode": settings.operation_mode,
                            "trading_style": settings.trading_style,
                        },
                    )
                    notifier.telegram(format_recommendation_message(top, rank=1, buy_amount_krw=settings.buy_amount_krw), rule_key="approval_request")

            try:
                exit_results = monitor_altcoin_exits(
                    config=config,
                    client=client,
                    settings=settings,
                    registry=registry,
                    positions=managed_positions,
                    notifier=notifier,
                )
                if exit_results:
                    notifier.step("보유 코인 매도 점검", f"{len(exit_results)}건의 자동매도 요청을 처리했습니다.", rule_key="order_result")
                else:
                    notifier.step("보유 코인 매도 점검", "BTC 외 보유 코인에 즉시 매도 조건이 없습니다.", telegram=False)
            except Exception as exc:
                append_history("auto_sell_failed", {"reason": str(exc), "operation_mode": settings.operation_mode})
                notifier.step("보유 코인 매도 점검 실패", str(exc), rule_key="risk_alert")

            notifier.step("전략 진단 데이터 조회", f"{config.market} {config.interval} 캔들 {config.candle_count}개를 가져옵니다.")
            candles = client.get_candles(config.market, config.interval, config.candle_count)
            notifier.step("지표 계산", "이동평균, RSI, ATR, MACD, 볼린저밴드를 계산합니다.")
            market_data = add_indicators(candles, config.ma_short, config.ma_mid, config.ma_long, config.rsi_period).dropna()
            if market_data.empty:
                notifier.step("지표 부족", "캔들 데이터가 더 쌓일 때까지 대기합니다.")
                time.sleep(config.loop_interval)
                continue

            notifier.step("전략 진단 현재가 조회", f"{config.market} 현재가를 가져옵니다.")
            current_price = client.get_current_price(config.market)
            notifier.step("포지션 확인", "보유 수량, 평균매수가, 평가금액을 계산합니다.")
            position = build_position(config, client, position)
            if position.has_position:
                position.highest_profit_rate = max(position.highest_profit_rate, position.profit_rate(current_price))

            if config.dry_run:
                available_krw = paper_krw
                total_equity = available_krw + (position.volume * current_price)
                managed_coin_count = 1 if position.has_position else 0
            else:
                total_equity, available_krw, managed_coin_count = fetch_total_portfolio_value(client)
                if total_equity <= 0:
                    total_equity = available_krw + (position.volume * current_price)
            profit_rate = position.profit_rate(current_price)
            notifier.step("전략 판단", "매수, 매도, 대기 신호를 생성합니다.")
            strategy = MovingAverageStrategy(config, settings)
            signal = strategy.generate_signal(market_data, position)
            if (
                signal.get("action") == "BUY"
                and settings.recommendation_enabled
                and settings.operation_mode >= 3
            ):
                signal = {
                    "action": "HOLD",
                    "reason": "전체 마켓 추천 엔진에서만 신규매수를 실행합니다.",
                    "confidence": 0.0,
                    "buy_ratio": 0.0,
                    "sell_ratio": 0.0,
                }
            update_market_status(
                market="업비트 KRW 마켓 전체",
                price=0.0,
                signal=str(signal.get("action", "HOLD")),
                reason=str(signal.get("reason", "")),
                dry_run=config.dry_run,
                real_trade_enabled=config.real_trade_enabled,
                available_krw=available_krw,
                total_equity=total_equity,
                position_volume=float(managed_coin_count),
                avg_buy_price=position.avg_buy_price,
                profit_rate=profit_rate,
                buy_count=position.buy_count,
                strategy_market=config.market,
            )
            notifier.signal(str(signal.get("action", "HOLD")), str(signal.get("reason", "")))

            print_status(config, current_price, position, market_data, signal)
            notifier.step("주문 검증", "리스크 조건을 확인하고 신호를 실행합니다.")
            action = str(signal.get("action", "HOLD"))
            if settings.approval_required and action in {"BUY", "SELL"}:
                approval_message = (
                    f"{config.market} {korean_action(action)} 신호가 발생했지만 승인 필요 설정 때문에 자동 실행하지 않았습니다. "
                    "대시보드 또는 텔레그램에서 추천/승인 흐름으로 확인하세요."
                )
                notifier.step("주문 승인 대기", approval_message, rule_key="approval_request")
                update_state(last_order_action=action, last_order_result=approval_message)
                result = None
            else:
                result = trader.execute_signal(signal, position, available_krw, current_price, total_equity)
            if result:
                notifier.step("주문 결과", str(result), rule_key="order_result")
                update_state(
                    last_order_action=action,
                    last_order_result=str(result),
                    last_market="업비트 KRW 마켓 전체",
                    operating_scope="업비트 KRW 마켓 전체",
                    strategy_market=config.market,
                    managed_coin_count=int(managed_coin_count),
                    available_krw=available_krw,
                    total_equity=total_equity,
                    position_volume=float(managed_coin_count),
                    avg_buy_price=position.avg_buy_price,
                    profit_rate=position.profit_rate(current_price),
                    buy_count=position.buy_count,
                )
            else:
                notifier.step("주문 결과", "실행된 주문이 없습니다.", telegram=False)
            if config.dry_run and result:
                if signal.get("action") == "BUY":
                    paper_krw = max(0.0, paper_krw - float(result.get("amount", 0)))
                elif signal.get("action") == "SELL":
                    paper_krw += float(result.get("volume", 0)) * current_price

        except KeyboardInterrupt:
            notifier.step("봇 정지", "키보드 입력으로 중단되었습니다.", rule_key="risk_alert")
            set_command("pause", "keyboard")
            break
        except Exception as exc:
            risk_manager.set_api_available(False)
            logger.exception("Main loop error: %s", exc)
            notifier.step("자동매매 오류", str(exc), rule_key="risk_alert")

        time.sleep(config.loop_interval)


if __name__ == "__main__":
    main()

"""Read-only FIFO audit of locally recorded Upbit fills.

The result covers orders recorded by this worker, not manual exchange trades.
Unknown opening inventory is reported as unmatched rather than assigned a cost.
"""

import argparse
import json
from collections import defaultdict, deque
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo


ZERO = Decimal(0)
TOLERANCE = Decimal('0.000000001')
HISTORY = Path(__file__).resolve().parents[1] / 'trade_history.jsonl'


def _filled_order(row):
    if row.get('execution_status') != 'filled':
        return None
    result = row.get('final_result') or {}
    fills = result.get('trades') or []
    if not fills:
        return None
    return {
        'time': str(row.get('time', '')),
        'market': str(row.get('market', '')),
        'kind': row.get('event'),
        'quantity': sum((Decimal(str(fill['volume'])) for fill in fills), ZERO),
        'funds': sum((Decimal(str(fill['funds'])) for fill in fills), ZERO),
        'fee': Decimal(str(result.get('paid_fee') or 0)),
        'strategy': ((row.get('recommendation') or {}).get('strategy_name')
                     or row.get('entry_strategy') or 'unknown'),
        'order_id': result.get('uuid'),
    }


def reconstruct(path=HISTORY):
    """Return sell orders and dated fees paid on every recorded fill."""
    inventory = defaultdict(deque)
    exits = []
    seen_orders = set()
    fee_events = []
    with Path(path).open(encoding='utf-8') as history:
        for line in history:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get('event') not in {'auto_buy', 'approve_buy', 'auto_sell', 'approve_sell'}:
                continue
            order = _filled_order(row)
            if not order or order['quantity'] <= 0 or not order['market']:
                continue
            order_id = order['order_id']
            if order_id and order_id in seen_orders:
                continue
            if order_id:
                seen_orders.add(order_id)
            fee_events.append({'time': order['time'], 'fee': order['fee']})
            if order['kind'] in {'auto_buy', 'approve_buy'}:
                inventory[order['market']].append({
                    'quantity': order['quantity'],
                    'unit_cost': (order['funds'] + order['fee']) / order['quantity'],
                    'strategy': order['strategy'],
                })
                continue
            remaining = order['quantity']
            cost = ZERO
            strategy_pnl = defaultdict(lambda: ZERO)
            while remaining > TOLERANCE and inventory[order['market']]:
                lot = inventory[order['market']][0]
                matched = min(remaining, lot['quantity'])
                matched_cost = matched * lot['unit_cost']
                matched_net = (order['funds'] - order['fee']) * matched / order['quantity']
                strategy_pnl[lot['strategy']] += matched_net - matched_cost
                cost += matched_cost
                lot['quantity'] -= matched
                remaining -= matched
                if lot['quantity'] <= TOLERANCE:
                    inventory[order['market']].popleft()
            exits.append({
                'time': order['time'], 'market': order['market'],
                'pnl': order['funds'] - order['fee'] - cost if remaining <= TOLERANCE else None,
                'sell_fee': order['fee'], 'strategy_pnl': dict(strategy_pnl)
                if remaining <= TOLERANCE else {},
                'unmatched_quantity': remaining if remaining > TOLERANCE else ZERO,
            })
    return exits, fee_events


def summarize(exits, start, end):
    selected = [row for row in exits if start <= row['time'][:10] < end]
    complete = all(row['pnl'] is not None for row in selected)
    values = [row['pnl'] for row in selected if row['pnl'] is not None]
    wins = sum(value > 0 for value in values)
    profit = sum((value for value in values if value > 0), ZERO)
    loss = -sum((value for value in values if value < 0), ZERO)
    strategies = defaultdict(lambda: ZERO)
    for row in selected:
        for name, pnl in row['strategy_pnl'].items():
            strategies[name] += pnl
    return {
        'start_kst': start, 'end_exclusive_kst': end,
        'closed_orders': len(selected),
        'unmatched_orders': len(selected) - len(values),
        'winning_orders': wins if complete else None,
        'realized_net_krw': str(sum(values, ZERO)) if complete else None,
        'win_rate': str(Decimal(wins) / len(values)) if values and complete else None,
        'profit_factor': str(profit / loss) if complete and loss > 0 else None,
        'sell_fees_krw': str(sum((row['sell_fee'] for row in selected), ZERO)),
        'by_entry_strategy_krw': {name: str(pnl) for name, pnl in sorted(strategies.items())}
        if complete else None,
    }


def paid_fees(fee_events, start, end):
    return str(sum((row['fee'] for row in fee_events
                    if start <= row['time'][:10] < end), ZERO))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--history', type=Path, default=HISTORY)
    parser.add_argument('--days', type=int, default=3)
    parser.add_argument('--end', help='exclusive KST date, YYYY-MM-DD')
    args = parser.parse_args()
    if args.days < 1:
        parser.error('--days must be positive')
    end = args.end or datetime.now(ZoneInfo('Asia/Seoul')).date().isoformat()
    start = (datetime.fromisoformat(end).date() - timedelta(days=args.days)).isoformat()
    exits, fee_events = reconstruct(args.history)
    report = summarize(exits, start, end)
    report['paid_fees_krw'] = paid_fees(fee_events, start, end)
    report['daily'] = [summarize(exits, day.isoformat(), (day + timedelta(days=1)).isoformat())
                       for day in (datetime.fromisoformat(start).date() + timedelta(days=offset)
                                   for offset in range(args.days))]
    report['recent_20'] = summarize(exits[-20:], '0000-01-01', '9999-12-31')
    report['all_recorded'] = summarize(exits, '0000-01-01', '9999-12-31')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

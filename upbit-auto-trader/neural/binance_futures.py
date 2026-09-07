"""Read-only Binance USD-M Futures collector.

This module intentionally contains no order, transfer, or withdrawal endpoint.
"""
import hashlib
import hmac
import os
import time
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlencode

import httpx
from dotenv import dotenv_values

from neural.store import Store, now


ACCOUNT = 'binance_futures'


def number(raw, *, signed=False):
    result = Decimal(str(raw or 0))
    if not result.is_finite() or (not signed and result < 0):
        raise ValueError('invalid numeric value')
    return result


def normalize(account, marks):
    prices = {row['symbol']: number(row['markPrice']) for row in marks}
    positions = []
    for row in account.get('positions', []):
        quantity = number(row.get('positionAmt'), signed=True)
        if quantity == 0:
            continue
        symbol = row['symbol']
        mark = prices.get(symbol)
        notional = abs(number(row.get('notional'), signed=True))
        if notional == 0 and mark is not None:
            notional = abs(quantity) * mark
        positions.append({
            'market': f'BINANCE-FUTURES:{symbol}',
            'symbol': symbol,
            'side': row.get('positionSide', 'BOTH'),
            'quantity': str(quantity),
            'entry_price': str(number(row.get('entryPrice'))),
            'price': str(mark) if mark is not None else None,
            'value': str(notional),
            'unrealized': str(number(row.get('unrealizedProfit'), signed=True)),
            'leverage': str(row.get('leverage', '')),
            'margin_type': 'isolated' if row.get('isolated') else 'cross',
        })
    equity = number(account.get('totalMarginBalance'))
    return {
        'as_of': now(), 'environment': 'LIVE_READ_ONLY', 'currency': 'USD',
        'cash': str(number(account.get('availableBalance'))), 'equity': str(equity),
        'priced_subtotal': str(equity),
        'unrealized': str(number(account.get('totalUnrealizedProfit'), signed=True)),
        'positions': positions,
        'unpriced': [p['symbol'] for p in positions if p['price'] is None],
        'source': 'binance_usdm_account_v3_and_mark_price',
    }


def signed_params(secret, timestamp):
    values = {'recvWindow': 5000, 'timestamp': timestamp}
    query = urlencode(values)
    values['signature'] = hmac.new(secret.encode(), query.encode(), hashlib.sha256).hexdigest()
    return values


def collect(store):
    env_path = Path(os.environ.get('BINANCE_ENV_FILE', Path(__file__).resolve().parents[1] / '.env'))
    config = dotenv_values(env_path, encoding='utf-8-sig')
    if str(config.get('BINANCE_FUTURES_ENABLED', 'false')).lower() != 'true':
        store.set_health('disabled', ACCOUNT)
        return
    api_key = config.get('BINANCE_API_KEY')
    secret = config.get('BINANCE_SECRET_KEY')
    if not api_key or not secret or api_key == 'your_api_key':
        store.set_health('missing_credentials', ACCOUNT)
        return
    base_url = config.get('BINANCE_FUTURES_BASE_URL', 'https://fapi.binance.com')
    with httpx.Client(base_url=base_url, timeout=10) as client:
        server_time = client.get('/fapi/v1/time')
        server_time.raise_for_status()
        timestamp = int(server_time.json()['serverTime'])
        response = client.get('/fapi/v3/account', params=signed_params(secret, timestamp),
                              headers={'X-MBX-APIKEY': api_key})
        response.raise_for_status()
        account = response.json()
        active = [p['symbol'] for p in account.get('positions', [])
                  if number(p.get('positionAmt'), signed=True) != 0]
        marks = []
        for symbol in active:
            mark = client.get('/fapi/v1/premiumIndex', params={'symbol': symbol})
            mark.raise_for_status()
            marks.append(mark.json())
        store.add_snapshot(normalize(account, marks), ACCOUNT)
        store.set_health('connected', ACCOUNT)


def run():
    store = Store()
    while True:
        try:
            collect(store)
        except httpx.HTTPStatusError as exc:
            store.set_health(f'http_{exc.response.status_code}', ACCOUNT)
        except Exception:
            store.set_health('collection_failed', ACCOUNT)
        time.sleep(30)


if __name__ == '__main__':
    run()

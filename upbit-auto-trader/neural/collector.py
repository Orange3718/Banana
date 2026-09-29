"""Read-only Upbit collector. No order API or Telegram access."""
import os
import time
import uuid
from decimal import Decimal
from pathlib import Path

import httpx
import jwt
from dotenv import dotenv_values

from neural.store import Store, now


def value(raw):
    n = Decimal(str(raw or 0))
    if not n.is_finite() or n < 0:
        raise ValueError('invalid monetary value')
    return n


def normalize(accounts, tickers):
    prices = {r['market']: value(r['trade_price']) for r in tickers}
    cash = Decimal(0)
    positions = []
    pnl = Decimal(0)
    missing = []
    for row in accounts:
        quantity = value(row.get('balance')) + value(row.get('locked'))
        symbol = row['currency']
        if symbol == 'KRW':
            cash += quantity
            continue
        if quantity == 0:
            continue
        market = f'KRW-{symbol}'
        price = prices.get(market)
        cost = value(row.get('avg_buy_price')) if row.get('unit_currency') == 'KRW' else None
        worth = quantity * price if price is not None else None
        unrealized = quantity * (price - cost) if price is not None and cost else None
        if price is None:
            missing.append(symbol)
        if unrealized is not None:
            pnl += unrealized
        positions.append({'market': market, 'symbol': symbol, 'quantity': str(quantity),
                          'price': str(price) if price is not None else None,
                          'value': str(worth) if worth is not None else None,
                          'unrealized': str(unrealized) if unrealized is not None else None})
    priced = cash + sum((Decimal(p['value']) for p in positions if p['value'] is not None), Decimal(0))
    return {'as_of': now(), 'environment': 'LIVE', 'currency': 'KRW', 'cash': str(cash),
            'equity': str(priced) if not missing else None, 'priced_subtotal': str(priced),
            'unrealized': str(pnl) if all(p['unrealized'] is not None for p in positions) else None,
            'positions': positions, 'unpriced': missing, 'source': 'upbit_accounts_and_ticker'}


def collect(store):
    env_path = Path(os.environ.get('UPBIT_ENV_FILE', Path(__file__).resolve().parents[1] / '.env'))
    config = dotenv_values(env_path, encoding='utf-8-sig')
    access = config.get('UPBIT_ACCESS_KEY')
    secret = config.get('UPBIT_SECRET_KEY')
    if not access or not secret or access == 'your_access_key':
        store.set_health('missing_credentials')
        return
    token = jwt.encode({'access_key': access, 'nonce': str(uuid.uuid4())}, secret, algorithm='HS512')
    with httpx.Client(base_url='https://api.upbit.com', timeout=10) as client:
        response = client.get('/v1/accounts', headers={'Authorization': f'Bearer {token}'})
        response.raise_for_status()
        accounts = response.json()
        markets = client.get('/v1/market/all')
        markets.raise_for_status()
        listed = {r['market'] for r in markets.json()}
        symbols = [f'KRW-{r["currency"]}' for r in accounts if f'KRW-{r["currency"]}' in listed]
        tickers = []
        if symbols:
            response = client.get('/v1/ticker', params={'markets': ','.join(symbols)})
            response.raise_for_status()
            tickers = response.json()
        store.add_snapshot(normalize(accounts, tickers))
        store.set_health('connected')


def run():
    store = Store()
    while True:
        try:
            collect(store)
        except httpx.HTTPStatusError as exc:
            store.set_health(f'http_{exc.response.status_code}')
        except Exception:
            store.set_health('collection_failed')
        time.sleep(30)


if __name__ == '__main__':
    run()

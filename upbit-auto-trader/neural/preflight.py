"""Cross-platform preflight checks that never use private API credentials."""
import json
import platform
import sys
from pathlib import Path

import httpx
from dotenv import dotenv_values

from neural.store import Store


ROOT = Path(__file__).resolve().parents[1]


def public_api_checks(client=None):
    own_client = client is None
    client = client or httpx.Client(timeout=8, follow_redirects=False)
    checks = {}
    targets = {
        'upbit_public': 'https://api.upbit.com/v1/market/all?is_details=false',
        'binance_futures_public': 'https://fapi.binance.com/fapi/v1/ping',
        'binance_server_time': 'https://fapi.binance.com/fapi/v1/time',
    }
    try:
        for name, url in targets.items():
            try:
                response = client.get(url)
                checks[name] = {'ok': response.status_code == 200, 'status_code': response.status_code}
            except httpx.HTTPError:
                checks[name] = {'ok': False, 'status_code': None}
    finally:
        if own_client:
            client.close()
    return checks


def report(env_path=None, client=None, store=None):
    path = Path(env_path or ROOT / '.env')
    config = dotenv_values(path, encoding='utf-8-sig') if path.exists() else {}
    db = store or Store()
    return {
        'platform': {'system': platform.system(), 'machine': platform.machine(),
                     'python': '.'.join(map(str, sys.version_info[:3]))},
        'files': {'env_exists': path.exists(),
                  'dashboard_built': (ROOT / 'apps/dashboard/dist/index.html').exists()},
        'credentials': {
            'upbit_configured': bool(config.get('UPBIT_ACCESS_KEY') and config.get('UPBIT_SECRET_KEY')),
            'binance_configured': bool(config.get('BINANCE_API_KEY') and config.get('BINANCE_SECRET_KEY')),
            'binance_enabled': str(config.get('BINANCE_FUTURES_ENABLED', 'false')).lower() == 'true',
        },
        'database': {
            'upbit': db.collector_status('upbit')['status'],
            'binance_futures': db.collector_status('binance_futures')['status'],
        },
        'public_apis': public_api_checks(client),
        'execution': 'read_only_dashboard; order endpoint not implemented',
    }


def main():
    print(json.dumps(report(), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

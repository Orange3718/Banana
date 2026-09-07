from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import jwt
import pandas as pd
import requests


class UpbitAPIError(RuntimeError):
    pass


@dataclass
class UpbitClient:
    access_key: str
    secret_key: str
    base_url: str = "https://api.upbit.com"
    timeout: int = 10
    max_retries: int = 3
    retry_delay: float = 0.5

    def _build_query_string(self, params: dict[str, Any] | None) -> str:
        if not params:
            return ""
        return urlencode(params, doseq=True)

    def _create_token(self, query_string: str = "") -> str:
        if not self.access_key or not self.secret_key:
            raise UpbitAPIError("UPBIT_ACCESS_KEY and UPBIT_SECRET_KEY are required for private API calls.")

        payload: dict[str, Any] = {
            "access_key": self.access_key,
            "nonce": str(uuid.uuid4()),
        }
        if query_string:
            payload["query_hash"] = hashlib.sha512(query_string.encode("utf-8")).hexdigest()
            payload["query_hash_alg"] = "SHA512"
        token = jwt.encode(payload, self.secret_key, algorithm="HS512")
        return token if isinstance(token, str) else token.decode("utf-8")

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        auth: bool = False,
    ) -> Any:
        url = f"{self.base_url}{path}"
        query_string = self._build_query_string(params)

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                headers = {"Accept": "application/json"}
                if auth:
                    headers["Authorization"] = f"Bearer {self._create_token(query_string)}"

                if method.upper() in {"GET", "DELETE"}:
                    response = requests.request(
                        method,
                        url,
                        params=params,
                        headers=headers,
                        timeout=self.timeout,
                    )
                else:
                    response = requests.request(
                        method,
                        url,
                        json=params,
                        headers={**headers, "Content-Type": "application/json"},
                        timeout=self.timeout,
                    )

                if response.status_code == 429 or 500 <= response.status_code < 600:
                    raise UpbitAPIError(f"Temporary API error {response.status_code}: {response.text}")

                if response.status_code >= 400:
                    raise UpbitAPIError(f"API error {response.status_code}: {response.text}")

                return response.json()
            except (requests.RequestException, UpbitAPIError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(self.retry_delay * attempt)

        raise UpbitAPIError(f"Request failed after retries: {last_error}")

    def get_current_price(self, market: str) -> float:
        data = self._request("GET", "/v1/ticker", {"markets": market})
        if not data:
            raise UpbitAPIError(f"No ticker data for {market}")
        return float(data[0]["trade_price"])

    def get_candles(self, market: str, interval: str = "minute5", count: int = 120) -> pd.DataFrame:
        path = self._candle_path(interval)
        data = self._request("GET", path, {"market": market, "count": count})
        candles = [
            {
                "timestamp": item["candle_date_time_kst"],
                "open": float(item["opening_price"]),
                "high": float(item["high_price"]),
                "low": float(item["low_price"]),
                "close": float(item["trade_price"]),
                "volume": float(item["candle_acc_trade_volume"]),
                "value": float(item["candle_acc_trade_price"]),
            }
            for item in reversed(data)
        ]
        return pd.DataFrame(candles)

    def _candle_path(self, interval: str) -> str:
        if interval.startswith("minute"):
            unit = interval.replace("minute", "")
            return f"/v1/candles/minutes/{unit}"
        mapping = {
            "day": "/v1/candles/days",
            "week": "/v1/candles/weeks",
            "month": "/v1/candles/months",
        }
        if interval not in mapping:
            raise ValueError(f"Unsupported interval: {interval}")
        return mapping[interval]

    def get_accounts(self) -> list[dict[str, Any]]:
        return self._request("GET", "/v1/accounts", auth=True)

    def get_balance(self, currency: str) -> dict[str, float]:
        for account in self.get_accounts():
            if account.get("currency") == currency:
                return {
                    "balance": float(account.get("balance", 0)),
                    "locked": float(account.get("locked", 0)),
                    "avg_buy_price": float(account.get("avg_buy_price", 0) or 0),
                }
        return {"balance": 0.0, "locked": 0.0, "avg_buy_price": 0.0}

    def get_available_krw(self) -> float:
        return self.get_balance("KRW")["balance"]

    def market_buy(self, market: str, krw_amount: float) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/orders",
            {"market": market, "side": "bid", "price": str(krw_amount), "ord_type": "price"},
            auth=True,
        )

    def market_sell(self, market: str, volume: float) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/orders",
            {"market": market, "side": "ask", "volume": str(volume), "ord_type": "market"},
            auth=True,
        )

    def limit_buy(self, market: str, price: float, volume: float) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/orders",
            {"market": market, "side": "bid", "price": str(price), "volume": str(volume), "ord_type": "limit"},
            auth=True,
        )

    def limit_sell(self, market: str, price: float, volume: float) -> dict[str, Any]:
        return self._request(
            "POST",
            "/v1/orders",
            {"market": market, "side": "ask", "price": str(price), "volume": str(volume), "ord_type": "limit"},
            auth=True,
        )

    def cancel_order(self, uuid_value: str) -> dict[str, Any]:
        return self._request("DELETE", "/v1/order", {"uuid": uuid_value}, auth=True)

    def get_order(self, uuid_value: str) -> dict[str, Any]:
        return self._request("GET", "/v1/order", {"uuid": uuid_value}, auth=True)

    def health_check(self) -> bool:
        try:
            self._request("GET", "/v1/market/all", {"isDetails": "false"})
            return True
        except Exception:
            return False

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import requests


class KiwoomAPIError(RuntimeError):
    pass


@dataclass
class KiwoomClient:
    """Minimal Kiwoom Securities REST client.

    Mirrors ``upbit_client.UpbitClient``'s shape (dataclass + retrying
    ``_send``) so the two brokers can be swapped behind the same call
    pattern. Defaults to the mock-trading domain; callers must opt into
    ``https://api.kiwoom.com`` explicitly once real keys exist.

    The exact header name carrying ``api_id`` (here ``api-id``, matching the
    KIS-style REST convention Kiwoom's REST API followed at design time) and
    the token response's expiry field are NOT verified against a live account
    or the official portal, since this was built without network access to
    kiwoom.com and without an issued App Key/Secret. Confirm both against
    https://openapi.kiwoom.com and a real (mock) token response before this
    client is used for anything beyond DRY_RUN testing.
    """

    app_key: str
    app_secret: str
    account_no: str = ""
    base_url: str = "https://mockapi.kiwoom.com"
    timeout: int = 10
    max_retries: int = 3
    retry_delay: float = 0.5

    _token: str | None = field(default=None, init=False, repr=False)
    _token_expires_at: float = field(default=0.0, init=False, repr=False)

    def _ensure_token(self) -> str:
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token
        if not self.app_key or not self.app_secret:
            raise KiwoomAPIError("KIWOOM_APP_KEY and KIWOOM_APP_SECRET are required for API calls.")

        response = self._send(
            "POST",
            "/oauth2/token",
            {"grant_type": "client_credentials", "appkey": self.app_key, "secretkey": self.app_secret},
            auth=False,
        )
        token = response.get("token") or response.get("access_token")
        if not token:
            raise KiwoomAPIError(f"Token response did not include an access token: {response}")

        # expires_in (seconds) is the documented shape; fall back to a
        # conservative 1-hour TTL if the live response uses a different key.
        expires_in = int(response.get("expires_in", 0) or 0)
        self._token = str(token)
        self._token_expires_at = time.time() + (expires_in or 3600)
        return self._token

    def _send(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        api_id: str | None = None,
        auth: bool = True,
    ) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json; charset=utf-8"}
        if auth:
            headers["Authorization"] = f"Bearer {self._ensure_token()}"
        if api_id:
            headers["api-id"] = api_id

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = requests.request(method, url, json=body, headers=headers, timeout=self.timeout)

                if response.status_code == 429 or 500 <= response.status_code < 600:
                    raise KiwoomAPIError(f"Temporary API error {response.status_code}: {response.text}")
                if response.status_code >= 400:
                    raise KiwoomAPIError(f"API error {response.status_code}: {response.text}")

                return response.json()
            except (requests.RequestException, KiwoomAPIError) as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                time.sleep(self.retry_delay * attempt)

        raise KiwoomAPIError(f"Request failed after retries: {last_error}")

    def get_account_balance(self, qry_tp: str = "1", dmst_stex_tp: str = "KRX") -> dict[str, Any]:
        """kt00004: account valuation / holdings snapshot."""
        return self._send("POST", "/api/dostk/acnt", {"qry_tp": qry_tp, "dmst_stex_tp": dmst_stex_tp}, api_id="kt00004")

    def get_top_change_rate(self, mrkt_tp: str = "000") -> list[dict[str, Any]]:
        """ka10027: 전일대비등락률상위 (top % change vs previous close), all-market by default.

        Field names verified live against api.kiwoom.com on 2026-09-28 (real
        account, read-only) — this is not a header/field guess like the
        order methods below. Returns the raw list under
        ``pred_pre_flu_rt_upper``, newest field names as Kiwoom returns them
        (e.g. ``stk_cd``, ``stk_nm``, ``cur_prc``, ``flu_rt``).
        """
        body = {
            "mrkt_tp": mrkt_tp,
            "sort_tp": "1",
            "trde_qty_cnd": "0000",
            "stk_cnd": "0",
            "crd_cnd": "0",
            "updown_incls": "1",
            "pric_cnd": "0",
            "trde_prica_cnd": "0",
            "stex_tp": "3",
        }
        response = self._send("POST", "/api/dostk/rkinfo", body, api_id="ka10027")
        return response.get("pred_pre_flu_rt_upper", [])

    def get_top_volume_today(self, mrkt_tp: str = "000") -> list[dict[str, Any]]:
        """ka10030: 당일거래량상위 (today's top trading volume), all-market by default.

        Field names verified live the same way as ``get_top_change_rate``.
        Returns the raw list under ``tdy_trde_qty_upper``.
        """
        body = {
            "mrkt_tp": mrkt_tp,
            "sort_tp": "1",
            "mang_stk_incls": "0",
            "crd_tp": "0",
            "stex_tp": "3",
            "trde_qty_tp": "0000",
            "pric_tp": "0",
            "trde_prica_tp": "0",
            "mrkt_open_tp": "0",
        }
        response = self._send("POST", "/api/dostk/rkinfo", body, api_id="ka10030")
        return response.get("tdy_trde_qty_upper", [])

    def get_order_book(self, stk_cd: str) -> dict[str, Any]:
        """ka10004: 주식호가 (10-level bid/ask order book) for one stock.

        This is a REST snapshot, not a WebSocket push feed — call it again
        to refresh. Field names verified live against api.kiwoom.com on
        2026-09-28 (real account, read-only, no order placed). Kiwoom
        prefixes every price with a +/- sign showing direction from the
        reference close, including bid/ask levels that are themselves
        always positive prices — callers should take abs() before display.
        """
        response = self._send("POST", "/api/dostk/mrkcond", {"stk_cd": stk_cd}, api_id="ka10004")
        asks = [
            {"price": response.get(f"sel_{n}th_pre_bid" if n > 1 else "sel_fpr_bid", "0"),
             "qty": response.get(f"sel_{n}th_pre_req" if n > 1 else "sel_fpr_req", "0")}
            for n in range(10, 0, -1)
        ]
        bids = [
            {"price": response.get(f"buy_{n}th_pre_bid" if n > 1 else "buy_fpr_bid", "0"),
             "qty": response.get(f"buy_{n}th_pre_req" if n > 1 else "buy_fpr_req", "0")}
            for n in range(1, 11)
        ]
        return {
            "stk_cd": stk_cd,
            "base_time": response.get("bid_req_base_tm", ""),
            "asks": asks,
            "bids": bids,
            "total_ask_qty": response.get("tot_sel_req", "0"),
            "total_bid_qty": response.get("tot_buy_req", "0"),
            "return_code": response.get("return_code"),
        }

    def _submit_order(
        self,
        api_id: str,
        stk_cd: str,
        ord_qty: int,
        trde_tp: str,
        ord_uv: str = "",
        cond_uv: str = "",
        dmst_stex_tp: str = "KRX",
    ) -> dict[str, Any]:
        body = {
            "dmst_stex_tp": dmst_stex_tp,
            "stk_cd": stk_cd,
            "ord_qty": str(ord_qty),
            "trde_tp": trde_tp,
            "ord_uv": str(ord_uv),
            "cond_uv": str(cond_uv),
        }
        return self._send("POST", "/api/dostk/ordr", body, api_id=api_id)

    def market_buy(self, stk_cd: str, quantity: int) -> dict[str, Any]:
        return self._submit_order("kt10000", stk_cd, quantity, trde_tp="3")

    def limit_buy(self, stk_cd: str, quantity: int, price: float) -> dict[str, Any]:
        return self._submit_order("kt10000", stk_cd, quantity, trde_tp="0", ord_uv=str(price))

    def market_sell(self, stk_cd: str, quantity: int) -> dict[str, Any]:
        return self._submit_order("kt10001", stk_cd, quantity, trde_tp="3")

    def limit_sell(self, stk_cd: str, quantity: int, price: float) -> dict[str, Any]:
        return self._submit_order("kt10001", stk_cd, quantity, trde_tp="0", ord_uv=str(price))

    def modify_order(
        self, orig_ord_no: str, stk_cd: str, quantity: int, price: float, dmst_stex_tp: str = "KRX"
    ) -> dict[str, Any]:
        body = {
            "dmst_stex_tp": dmst_stex_tp,
            "orig_ord_no": orig_ord_no,
            "stk_cd": stk_cd,
            "mdfy_qty": str(quantity),
            "mdfy_uv": str(price),
        }
        return self._send("POST", "/api/dostk/ordr", body, api_id="kt10002")

    def cancel_order(self, orig_ord_no: str, stk_cd: str, quantity: int, dmst_stex_tp: str = "KRX") -> dict[str, Any]:
        body = {
            "dmst_stex_tp": dmst_stex_tp,
            "orig_ord_no": orig_ord_no,
            "stk_cd": stk_cd,
            "cncl_qty": str(quantity),
        }
        return self._send("POST", "/api/dostk/ordr", body, api_id="kt10003")

    def health_check(self) -> bool:
        try:
            self._ensure_token()
            return True
        except Exception:
            return False

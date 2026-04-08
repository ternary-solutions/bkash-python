from __future__ import annotations

from typing import Any, Mapping

import httpx

from bkash_pgw_tokenized.config import _Credentials
from bkash_pgw_tokenized.exceptions import BkashHttpError


class Bkash:
    """
    Async HTTP client for bKash Tokenized Checkout.

    Pass the merchant **config** mapping (same shape as JSON / env / settings):

        client = Bkash({
            "app_key": "...",
            "app_secret": "...",
            "username": "...",
            "password": "...",
            "sandbox": True,
        })
    """

    def __init__(
        self,
        config: Mapping[str, Any],
        *,
        timeout: float = 30.0,
        connect_timeout: float | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._creds = _Credentials(config)
        self._base = self._creds.normalized_base_url()
        self._timeout = timeout
        self._connect_timeout = connect_timeout
        self._transport = transport

    def _url(self, path: str) -> str:
        return f"{self._base}/{path.lstrip('/')}"

    def _token_headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "username": self._creds.username,
            "password": self._creds.password,
        }

    def _auth_headers(self, id_token: str) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": id_token,
            "X-APP-Key": self._creds.app_key,
        }

    async def _post_json(
        self,
        path: str,
        *,
        headers: dict[str, str],
        json_body: dict[str, Any],
        timeout: httpx.Timeout | None = None,
    ) -> dict[str, Any]:
        t = timeout or httpx.Timeout(self._timeout)
        client_kw: dict[str, Any] = {"timeout": t}
        if self._transport is not None:
            client_kw["transport"] = self._transport
        async with httpx.AsyncClient(**client_kw) as client:
            r = await client.post(self._url(path), headers=headers, json=json_body)
        if r.is_error:
            body: Any
            try:
                body = r.json()
            except Exception:
                body = r.text
            raise BkashHttpError(
                f"bKash API HTTP {r.status_code}",
                status_code=r.status_code,
                response_body=body,
            )
        return r.json()

    async def grant_token(self) -> dict[str, Any]:
        return await self._post_json(
            "tokenized/checkout/token/grant",
            headers=self._token_headers(),
            json_body={
                "app_key": self._creds.app_key,
                "app_secret": self._creds.app_secret,
            },
        )

    async def refresh_token(self, refresh_token: str) -> dict[str, Any]:
        return await self._post_json(
            "tokenized/checkout/token/refresh",
            headers=self._token_headers(),
            json_body={
                "app_key": self._creds.app_key,
                "app_secret": self._creds.app_secret,
                "refresh_token": refresh_token,
            },
        )

    async def create_payment(
        self,
        id_token: str,
        *,
        mode: str,
        payer_reference: str,
        callback_url: str,
        amount: str,
        currency: str,
        intent: str,
        merchant_invoice_number: str,
    ) -> dict[str, Any]:
        return await self._post_json(
            "tokenized/checkout/create",
            headers=self._auth_headers(id_token),
            json_body={
                "mode": mode,
                "payerReference": payer_reference,
                "callbackURL": callback_url,
                "amount": amount,
                "currency": currency,
                "intent": intent,
                "merchantInvoiceNumber": merchant_invoice_number,
            },
        )

    async def execute_payment(self, id_token: str, payment_id: str) -> dict[str, Any]:
        connect = self._connect_timeout if self._connect_timeout is not None else 10.0
        timeout = httpx.Timeout(self._timeout, connect=connect)
        client_kw: dict[str, Any] = {"timeout": timeout}
        if self._transport is not None:
            client_kw["transport"] = self._transport
        async with httpx.AsyncClient(**client_kw) as client:
            r = await client.post(
                self._url("tokenized/checkout/execute"),
                headers=self._auth_headers(id_token),
                json={"paymentID": payment_id},
            )
        if r.is_error:
            body: Any
            try:
                body = r.json()
            except Exception:
                body = r.text
            raise BkashHttpError(
                f"bKash API HTTP {r.status_code}",
                status_code=r.status_code,
                response_body=body,
            )
        try:
            return r.json()
        except Exception:
            return {}

    async def payment_status(self, id_token: str, payment_id: str) -> dict[str, Any]:
        return await self._post_json(
            "tokenized/checkout/payment/status",
            headers=self._auth_headers(id_token),
            json_body={"paymentID": payment_id},
        )

    async def search_transaction(self, id_token: str, trx_id: str) -> dict[str, Any]:
        return await self._post_json(
            "tokenized/checkout/general/searchTransaction",
            headers=self._auth_headers(id_token),
            json_body={"trxID": trx_id},
        )

    async def refund(
        self,
        id_token: str,
        *,
        payment_id: str,
        trx_id: str,
        amount: str,
        sku: str,
        reason: str,
    ) -> dict[str, Any]:
        return await self._post_json(
            "tokenized/checkout/payment/refund",
            headers=self._auth_headers(id_token),
            json_body={
                "paymentID": payment_id,
                "trxID": trx_id,
                "amount": amount,
                "sku": sku,
                "reason": reason,
            },
        )


AsyncBkashClient = Bkash

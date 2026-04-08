import json

import httpx
import pytest

from bkash_pgw_tokenized import Bkash, BkashHttpError

from tests.helpers import SAMPLE_BASE, make_transport


@pytest.mark.asyncio
async def test_grant_token_headers_and_body(config: dict[str, str | bool]) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content.decode())
        return httpx.Response(200, json={"statusCode": "0000", "id_token": "id-1"})

    client = Bkash(config, transport=httpx.MockTransport(handler))
    result = await client.grant_token()
    assert result["id_token"] == "id-1"
    h = captured["headers"]
    assert isinstance(h, dict)
    assert h.get("username") == "user"
    assert h.get("password") == "pass"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["app_key"] == "app_key"
    assert body["app_secret"] == "app_secret"


@pytest.mark.asyncio
async def test_refresh_token(config: dict[str, str | bool]) -> None:
    transport = make_transport(
        {
            "tokenized/checkout/token/refresh": (
                200,
                {"statusCode": "0000", "id_token": "new", "refresh_token": "r2"},
            ),
        }
    )
    client = Bkash(config, transport=transport)
    data = await client.refresh_token("r1")
    assert data["id_token"] == "new"


@pytest.mark.asyncio
async def test_create_payment_uses_auth_headers(config: dict[str, str | bool]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers.get("authorization") == "tok"
        assert request.headers.get("x-app-key") == "app_key"
        body = json.loads(request.content.decode())
        assert body["merchantInvoiceNumber"] == "INV1"
        assert body["payerReference"] == "P1"
        return httpx.Response(200, json={"statusCode": "0000"})

    client = Bkash(config, transport=httpx.MockTransport(handler))
    await client.create_payment(
        "tok",
        mode="0011",
        payer_reference="P1",
        callback_url="https://cb.example/hook",
        amount="10.00",
        currency="BDT",
        intent="sale",
        merchant_invoice_number="INV1",
    )


@pytest.mark.asyncio
async def test_search_transaction_sends_trx_id(config: dict[str, str | bool]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url.path).endswith("general/searchTransaction")
        body = json.loads(request.content.decode())
        assert body == {"trxID": "TRX123"}
        return httpx.Response(200, json={"statusCode": "0000", "trxID": "TRX123"})

    client = Bkash(config, transport=httpx.MockTransport(handler))
    await client.search_transaction("tok", "TRX123")


@pytest.mark.asyncio
async def test_http_error_includes_body(config: dict[str, str | bool]) -> None:
    transport = make_transport(
        {"tokenized/checkout/token/grant": (401, {"errorMessage": "nope"})},
    )
    client = Bkash(config, transport=transport)
    with pytest.raises(BkashHttpError) as ei:
        await client.grant_token()
    assert ei.value.status_code == 401
    assert ei.value.response_body == {"errorMessage": "nope"}


@pytest.mark.asyncio
async def test_execute_payment_invalid_json_returns_empty_dict(config: dict[str, str | bool]) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json")

    client = Bkash(config, transport=httpx.MockTransport(handler))
    out = await client.execute_payment("tok", "pid")
    assert out == {}


@pytest.mark.asyncio
async def test_url_joins_base_without_double_slash(config: dict[str, str | bool]) -> None:
    cfg = {**config, "base_url": SAMPLE_BASE + "/"}

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url.path).startswith("/v1.2.0-beta/tokenized/checkout/token/grant")
        return httpx.Response(200, json={"statusCode": "0000", "id_token": "x"})

    client = Bkash(cfg, transport=httpx.MockTransport(handler))
    await client.grant_token()

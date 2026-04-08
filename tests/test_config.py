import pytest

from bkash_pgw_tokenized import (
    BKASH_TOKENIZED_LIVE_BASE_URL,
    BKASH_TOKENIZED_SANDBOX_BASE_URL,
    Bkash,
)


def test_bkash_requires_config_dict() -> None:
    with pytest.raises(TypeError):
        Bkash()  # type: ignore[call-arg]


def test_bkash_rejects_empty_required_keys() -> None:
    with pytest.raises(ValueError, match="app_key"):
        Bkash({})


@pytest.mark.asyncio
async def test_default_sandbox_base_url() -> None:
    import httpx

    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return httpx.Response(200, json={"statusCode": "0000", "id_token": "t"})

    cfg = {
        "app_key": "a",
        "app_secret": "b",
        "username": "u",
        "password": "p",
        "sandbox": True,
    }
    client = Bkash(cfg, transport=httpx.MockTransport(handler))
    await client.grant_token()
    assert urls[0].startswith(BKASH_TOKENIZED_SANDBOX_BASE_URL.rstrip("/"))


@pytest.mark.asyncio
async def test_default_live_base_url() -> None:
    import httpx

    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return httpx.Response(200, json={"statusCode": "0000", "id_token": "t"})

    cfg = {
        "app_key": "a",
        "app_secret": "b",
        "username": "u",
        "password": "p",
        "sandbox": False,
    }
    client = Bkash(cfg, transport=httpx.MockTransport(handler))
    await client.grant_token()
    assert urls[0].startswith(BKASH_TOKENIZED_LIVE_BASE_URL.rstrip("/"))


@pytest.mark.asyncio
async def test_base_url_override() -> None:
    import httpx

    urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        urls.append(str(request.url))
        return httpx.Response(200, json={"statusCode": "0000", "id_token": "t"})

    cfg = {
        "app_key": "a",
        "app_secret": "b",
        "username": "u",
        "password": "p",
        "sandbox": False,
        "base_url": "https://custom.example/api/",
    }
    client = Bkash(cfg, transport=httpx.MockTransport(handler))
    await client.grant_token()
    assert urls[0].startswith("https://custom.example/api/tokenized/checkout/token/grant")


def test_async_bkash_client_is_alias() -> None:
    from bkash_pgw_tokenized import AsyncBkashClient

    assert AsyncBkashClient is Bkash

import httpx
import pytest

from bkash_pgw_tokenized import Bkash, MemoryTokenStore, ensure_id_token
from tests.helpers import make_transport


@pytest.mark.asyncio
async def test_ensure_id_token_uses_cached_when_valid(config: dict[str, str | bool]) -> None:
    from datetime import datetime, timedelta, timezone

    from bkash_pgw_tokenized import TokenState

    store = MemoryTokenStore()

    future = datetime.now(timezone.utc) + timedelta(hours=1)
    await store.save(
        TokenState(id_token="cached", refresh_token=None, id_token_expires_at=future),
    )

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("should not call network when token valid")

    client = Bkash(config, transport=httpx.MockTransport(handler))
    tok = await ensure_id_token(store, client)
    assert tok == "cached"


@pytest.mark.asyncio
async def test_ensure_id_token_refreshes_when_expired(config: dict[str, str | bool]) -> None:
    from datetime import datetime, timedelta, timezone

    from bkash_pgw_tokenized import TokenState

    store = MemoryTokenStore()
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    await store.save(
        TokenState(
            id_token="old",
            refresh_token="r1",
            id_token_expires_at=past,
        )
    )

    transport = make_transport(
        {
            "tokenized/checkout/token/refresh": (
                200,
                {
                    "statusCode": "0000",
                    "id_token": "from-refresh",
                    "refresh_token": "r1",
                    "expires_in": "not-a-number",
                },
            ),
        }
    )
    client = Bkash(config, transport=transport)
    tok = await ensure_id_token(store, client)
    assert tok == "from-refresh"
    loaded = await store.load()
    assert loaded is not None
    assert loaded.id_token == "from-refresh"
    assert loaded.id_token_expires_at is not None


@pytest.mark.asyncio
async def test_ensure_id_token_grants_after_failed_refresh(config: dict[str, str | bool]) -> None:
    from datetime import datetime, timedelta, timezone

    from bkash_pgw_tokenized import TokenState

    store = MemoryTokenStore()
    await store.save(
        TokenState(
            id_token="old",
            refresh_token="bad",
            id_token_expires_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
    )

    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        path = str(request.url.path)
        if path.endswith("refresh"):
            calls.append("refresh")
            return httpx.Response(200, json={"statusCode": "2001", "errorMessage": "bad"})
        if path.endswith("grant"):
            calls.append("grant")
            return httpx.Response(
                200,
                json={
                    "statusCode": "0000",
                    "id_token": "from-grant",
                    "refresh_token": "nr",
                    "expires_in": "3600",
                },
            )
        return httpx.Response(404)

    client = Bkash(config, transport=httpx.MockTransport(handler))
    tok = await ensure_id_token(store, client)
    assert tok == "from-grant"
    assert calls == ["refresh", "grant"]


@pytest.mark.asyncio
async def test_ensure_id_token_grants_when_store_is_empty(config: dict[str, str | bool]) -> None:
    store = MemoryTokenStore()
    transport = make_transport(
        {
            "tokenized/checkout/token/grant": (
                200,
                {
                    "statusCode": "0000",
                    "id_token": "from-grant",
                    "refresh_token": "r1",
                },
            ),
        }
    )
    client = Bkash(config, transport=transport)

    tok = await ensure_id_token(store, client)

    assert tok == "from-grant"
    loaded = await store.load()
    assert loaded is not None
    assert loaded.refresh_token == "r1"
    assert loaded.id_token_expires_at is not None


@pytest.mark.asyncio
async def test_ensure_id_token_raises_when_grant_fails(config: dict[str, str | bool]) -> None:
    store = MemoryTokenStore()
    transport = make_transport(
        {
            "tokenized/checkout/token/grant": (
                200,
                {"statusCode": "2001", "errorMessage": "grant failed"},
            ),
        }
    )
    client = Bkash(config, transport=transport)

    with pytest.raises(RuntimeError, match="grant failed"):
        await ensure_id_token(store, client)

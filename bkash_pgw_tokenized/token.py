from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol, runtime_checkable

from bkash_pgw_tokenized.client import Bkash


def _parse_expires_in(raw: Any) -> int:
    if raw is None:
        return 3600
    try:
        return int(str(raw), 10)
    except ValueError:
        return 3600


def _token_body_ok(data: dict[str, Any]) -> bool:
    code = str(data.get("statusCode", ""))
    return code == "0000" and bool(data.get("id_token"))


@dataclass
class TokenState:
    id_token: str | None = None
    refresh_token: str | None = None
    id_token_expires_at: datetime | None = None


@runtime_checkable
class TokenStore(Protocol):
    async def load(self) -> TokenState | None: ...

    async def save(self, state: TokenState) -> None: ...


class MemoryTokenStore:
    """In-process token cache (suitable for single-worker dev only)."""

    def __init__(self) -> None:
        self._state: TokenState | None = None

    async def load(self) -> TokenState | None:
        return self._state

    async def save(self, state: TokenState) -> None:
        self._state = state


async def ensure_id_token(
    store: TokenStore,
    client: Bkash,
    *,
    skew_seconds: int = 60,
) -> str:
    """
    Return a valid id_token, using refresh_token when possible and grant otherwise.

    Persists updates through ``store`` (same flow as the demo API's Postgres singleton row).
    """
    row = await store.load()
    if row is None:
        row = TokenState()

    now = datetime.now(timezone.utc)
    skew = timedelta(seconds=skew_seconds)

    if row.id_token and row.id_token_expires_at and row.id_token_expires_at - skew > now:
        return row.id_token

    if row.refresh_token:
        data = await client.refresh_token(row.refresh_token)
        if _token_body_ok(data):
            id_token = str(data["id_token"])
            row = replace(
                row,
                id_token=id_token,
                refresh_token=data.get("refresh_token") or row.refresh_token,
                id_token_expires_at=now
                + timedelta(seconds=_parse_expires_in(data.get("expires_in"))),
            )
            await store.save(row)
            return id_token
        row = replace(row, refresh_token=None)
        await store.save(row)

    data = await client.grant_token()
    if not _token_body_ok(data):
        msg = data.get("statusMessage") or data.get("errorMessage") or "Grant token failed"
        raise RuntimeError(str(msg))

    id_token = str(data["id_token"])
    row = replace(
        row,
        id_token=id_token,
        refresh_token=data.get("refresh_token"),
        id_token_expires_at=now + timedelta(seconds=_parse_expires_in(data.get("expires_in"))),
    )
    await store.save(row)
    return id_token

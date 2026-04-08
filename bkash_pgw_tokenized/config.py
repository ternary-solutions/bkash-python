from __future__ import annotations

from types import MappingProxyType
from typing import Any, ItemsView, Iterator, KeysView, Mapping, TypedDict, ValuesView, cast

# Default roots for bKash Tokenized Checkout (paths append e.g. tokenized/checkout/...).
# Override with ``"base_url"`` in the config dict if bKash publishes a different host.
BKASH_TOKENIZED_SANDBOX_BASE_URL = "https://tokenized.sandbox.bka.sh/v1.2.0-beta"
BKASH_TOKENIZED_LIVE_BASE_URL = "https://tokenized.pay.bka.sh/v1.2.0-beta"


class BkashConfigRequired(TypedDict):
    app_key: str
    app_secret: str
    username: str
    password: str


class BkashConfig(BkashConfigRequired, total=False):
    """Type hint for the ``config`` dict passed to ``Bkash(config)``."""

    sandbox: bool
    base_url: str | None


class _Credentials(Mapping[str, Any]):
    """Normalized merchant config (internal)."""

    __slots__ = ("_data",)

    def __init__(self, config: Mapping[str, Any]) -> None:
        merged: dict[str, Any] = {"sandbox": True, "base_url": None}
        merged.update(dict(config))

        for key in ("app_key", "app_secret", "username", "password"):
            val = merged.get(key)
            if val is None or (isinstance(val, str) and not val.strip()):
                raise ValueError(f"Bkash config: missing or empty {key!r}")

        merged["sandbox"] = bool(merged["sandbox"])
        if merged.get("base_url") is not None:
            merged["base_url"] = str(merged["base_url"]).strip() or None

        self._data = MappingProxyType(
            {
                "app_key": str(merged["app_key"]),
                "app_secret": str(merged["app_secret"]),
                "username": str(merged["username"]),
                "password": str(merged["password"]),
                "sandbox": merged["sandbox"],
                "base_url": merged["base_url"],
            }
        )

    def to_dict(self) -> dict[str, Any]:
        return dict(self._data)

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)

    def keys(self) -> KeysView[str]:
        return self._data.keys()

    def values(self) -> ValuesView[Any]:
        return self._data.values()

    def items(self) -> ItemsView[str, Any]:
        return self._data.items()

    @property
    def app_key(self) -> str:
        return cast(str, self._data["app_key"])

    @property
    def app_secret(self) -> str:
        return cast(str, self._data["app_secret"])

    @property
    def username(self) -> str:
        return cast(str, self._data["username"])

    @property
    def password(self) -> str:
        return cast(str, self._data["password"])

    @property
    def sandbox(self) -> bool:
        return cast(bool, self._data["sandbox"])

    @property
    def base_url(self) -> str | None:
        return cast(str | None, self._data["base_url"])

    def normalized_base_url(self) -> str:
        if self.base_url is not None:
            return self.base_url.rstrip("/")
        root = BKASH_TOKENIZED_SANDBOX_BASE_URL if self.sandbox else BKASH_TOKENIZED_LIVE_BASE_URL
        return root.rstrip("/")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, _Credentials):
            return NotImplemented
        return dict(self._data) == dict(other._data)

    def __hash__(self) -> int:
        return hash(tuple(sorted(self._data.items())))

    def __repr__(self) -> str:
        return (
            "_Credentials({"
            f"'app_key': '…', 'app_secret': '…', 'username': '…', 'password': '…', "
            f"'sandbox': {self.sandbox!r}, 'base_url': {self.base_url!r}"
            "})"
        )

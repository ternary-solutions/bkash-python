from __future__ import annotations

from typing import Any


class BkashHttpError(Exception):
    """Raised when the bKash API returns a non-success HTTP status."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int,
        response_body: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body

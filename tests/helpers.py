import httpx

SAMPLE_BASE = "https://sandbox.example/v1.2.0-beta"


def make_transport(routes: dict[str, tuple[int, dict]]) -> httpx.MockTransport:
    """Map URL path suffix (e.g. token/grant) to (status, json_body)."""

    def handler(request: httpx.Request) -> httpx.Response:
        path = str(request.url.path)
        for suffix, (status, payload) in routes.items():
            if path.rstrip("/").endswith(suffix.rstrip("/")):
                return httpx.Response(status, json=payload)
        return httpx.Response(404, text=f"unmocked: {path}")

    return httpx.MockTransport(handler)

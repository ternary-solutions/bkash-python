import pytest

SAMPLE_BASE = "https://sandbox.example/v1.2.0-beta"


@pytest.fixture
def config() -> dict[str, str | bool]:
    return {
        "app_key": "app_key",
        "app_secret": "app_secret",
        "username": "user",
        "password": "pass",
        "sandbox": True,
        "base_url": SAMPLE_BASE,
    }

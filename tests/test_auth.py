"""Tests for auth handler method guards."""

import sys
import types
from pathlib import Path

import pytest

# Make src and src/handlers importable without triggering package side effects.
src_path = Path(__file__).resolve().parent.parent / "src"
handlers_path = src_path / "handlers"
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(handlers_path))


class _MockWorkersResponse:
    @staticmethod
    def json(data, status=200, headers=None):
        return types.SimpleNamespace(body=data, status=status, headers=headers or {})


# Stub workers module required by handlers/auth.py imports.
sys.modules.setdefault("workers", types.SimpleNamespace(Response=_MockWorkersResponse))

import auth as auth_handler  # pyright: ignore[reportMissingImports]


class MockRequest:
    def __init__(self, method: str, url: str = "https://example.com/auth/signin"):
        self.method = method
        self.url = url

    async def text(self):
        return ""


class EmptyEnv:
    pass


@pytest.mark.asyncio
async def test_signin_wrong_method_returns_405_before_jwt_check():
    request = MockRequest(method="GET")
    response = await auth_handler.handle_signin(request, EmptyEnv(), {}, {}, "/auth/signin")

    assert response.status == 405
    assert response.headers.get("Allow") == "POST"


@pytest.mark.asyncio
async def test_verify_email_wrong_method_returns_405_before_db_or_jwt(monkeypatch):
    async def _boom_get_db(_env):
        raise AssertionError("get_db_safe should not be called for wrong method")

    monkeypatch.setattr(auth_handler, "get_db_safe", _boom_get_db)

    request = MockRequest(method="POST", url="https://example.com/auth/verify-email")
    response = await auth_handler.handle_verify_email(
        request, EmptyEnv(), {}, {}, "/auth/verify-email"
    )

    assert response.status == 405
    assert response.headers.get("Allow") == "GET"

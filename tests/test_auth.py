"""Tests for auth handler method guards."""

import importlib.util
import sys
import types
from pathlib import Path

import pytest

class _MockWorkersResponse:
    @staticmethod
    def json(data, status=200, headers=None):
        return types.SimpleNamespace(body=data, status=status, headers=headers or {})


@pytest.fixture
def auth_handler_module(monkeypatch):
    """Load handlers/auth.py with an isolated workers stub per test."""
    monkeypatch.setitem(
        sys.modules,
        "workers",
        types.SimpleNamespace(Response=_MockWorkersResponse),
    )

    module_path = Path(__file__).resolve().parent.parent / "src" / "handlers" / "auth.py"
    spec = importlib.util.spec_from_file_location("auth_handler_under_test", module_path)
    assert spec is not None and spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MockRequest:
    def __init__(self, method: str, url: str = "https://example.com/auth/signin"):
        self.method = method
        self.url = url

    async def text(self):
        return ""


class EmptyEnv:
    pass


@pytest.mark.asyncio
async def test_signin_wrong_method_returns_405_before_jwt_check(auth_handler_module):
    request = MockRequest(method="GET")
    response = await auth_handler_module.handle_signin(
        request, EmptyEnv(), {}, {}, "/auth/signin"
    )

    assert response.status == 405
    assert response.headers.get("Allow") == "POST"


@pytest.mark.asyncio
async def test_verify_email_wrong_method_returns_405_before_db_or_jwt(
    monkeypatch,
    auth_handler_module,
):
    async def _boom_get_db(_env):
        raise AssertionError("get_db_safe should not be called for wrong method")

    monkeypatch.setattr(auth_handler_module, "get_db_safe", _boom_get_db)

    request = MockRequest(method="POST", url="https://example.com/auth/verify-email")
    response = await auth_handler_module.handle_verify_email(
        request, EmptyEnv(), {}, {}, "/auth/verify-email"
    )

    assert response.status == 405
    assert response.headers.get("Allow") == "GET"


@pytest.mark.asyncio
async def test_signup_wrong_method_returns_405_before_db_or_jwt(
    monkeypatch,
    auth_handler_module,
):
    async def _boom_get_db(_env):
        raise AssertionError("get_db_safe should not be called for wrong method")

    monkeypatch.setattr(auth_handler_module, "get_db_safe", _boom_get_db)

    request = MockRequest(method="GET", url="https://example.com/auth/signup")
    response = await auth_handler_module.handle_signup(
        request, EmptyEnv(), {}, {}, "/auth/signup"
    )

    assert response.status == 405
    assert response.headers.get("Allow") == "POST"

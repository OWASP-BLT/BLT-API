"""
Tests for signup input validation (issue #57).

Validates username format, email format, and password strength
in the POST /auth/signup handler.
"""

import sys
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

_mock_workers = MagicMock()


class _MockResponse:
    def __init__(self, data, status=200):
        self.data = data
        self.status = status
        self.body = json.dumps(data)

    @classmethod
    def json(cls, data, status=200, **kwargs):
        return cls(data, status)


_mock_workers.Response = _MockResponse
sys.modules.setdefault("workers", _mock_workers)
sys.modules.setdefault("libs", MagicMock())
sys.modules.setdefault("libs.db", MagicMock())
sys.modules.setdefault("libs.constant", MagicMock(__HASHING_ITERATIONS=1))
sys.modules.setdefault("libs.jwt_utils", MagicMock())
sys.modules.setdefault("models", MagicMock())
sys.modules.setdefault("services", MagicMock())
sys.modules.setdefault("services.email_service", MagicMock())
sys.modules.setdefault("services.email_templates", MagicMock())

from handlers.auth import handle_signup  # noqa: E402


class MockRequest:
    def __init__(self, method="POST", body=None):
        self.method = method
        self._body = body

    async def text(self):
        if self._body is None:
            return ""
        if isinstance(self._body, dict):
            return json.dumps(self._body)
        return str(self._body)


class MockEnv:
    JWT_SECRET = "test-secret-key"
    BLT_API_BASE_URL = "http://localhost:8787"
    MAILGUN_API_KEY = "test-key"
    MAILGUN_DOMAIN = "test.mailgun.org"


def _valid_body(**overrides):
    """Return a valid signup body, with optional overrides."""
    base = {
        "username": "validuser",
        "email": "valid@example.com",
        "password": "securepass123",
    }
    base.update(overrides)
    return base


# ─── Username validation ────────────────────────────────────────────────


class TestUsernameValidation:
    @pytest.mark.asyncio
    async def test_username_too_short_returns_400(self):
        body = _valid_body(username="ab")
        resp = await handle_signup(MockRequest(body=body), MockEnv(), {}, {}, "/auth/signup")
        assert resp.status == 400
        data = resp.data if isinstance(resp.data, dict) else json.loads(resp.body)
        assert "3-150" in data.get("message", "")

    @pytest.mark.asyncio
    async def test_username_empty_after_trim_returns_400(self):
        body = _valid_body(username="   ")
        resp = await handle_signup(MockRequest(body=body), MockEnv(), {}, {}, "/auth/signup")
        assert resp.status == 400

    @pytest.mark.asyncio
    async def test_username_too_long_returns_400(self):
        body = _valid_body(username="a" * 151)
        resp = await handle_signup(MockRequest(body=body), MockEnv(), {}, {}, "/auth/signup")
        assert resp.status == 400

    @pytest.mark.asyncio
    async def test_username_with_special_chars_returns_400(self):
        body = _valid_body(username="user@name!")
        resp = await handle_signup(MockRequest(body=body), MockEnv(), {}, {}, "/auth/signup")
        assert resp.status == 400
        data = resp.data if isinstance(resp.data, dict) else json.loads(resp.body)
        assert "letters" in data.get("message", "").lower() or "underscore" in data.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_username_with_spaces_returns_400(self):
        body = _valid_body(username="user name")
        resp = await handle_signup(MockRequest(body=body), MockEnv(), {}, {}, "/auth/signup")
        assert resp.status == 400

    @pytest.mark.asyncio
    async def test_valid_username_with_underscores_accepted(self):
        body = _valid_body(username="valid_user_123")
        mock_user_cls = MagicMock()
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.first = AsyncMock(return_value=None)
        mock_user_cls.objects.return_value = mock_qs
        mock_user_cls.create = AsyncMock(return_value={"id": 1})

        mock_email = MagicMock()
        mock_email.send_verification_email = AsyncMock(return_value=(200, "OK"))

        with patch("handlers.auth.get_db_safe", AsyncMock(return_value=MagicMock())), \
             patch("handlers.auth.User", mock_user_cls), \
             patch("handlers.auth.EmailService", return_value=mock_email), \
             patch("handlers.auth.generate_jwt_token", return_value="fake.token"):
            resp = await handle_signup(MockRequest(body=body), MockEnv(), {}, {}, "/auth/signup")

        assert resp.status == 201

    @pytest.mark.asyncio
    async def test_username_exactly_3_chars_accepted(self):
        body = _valid_body(username="abc")
        mock_user_cls = MagicMock()
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.first = AsyncMock(return_value=None)
        mock_user_cls.objects.return_value = mock_qs
        mock_user_cls.create = AsyncMock(return_value={"id": 1})

        mock_email = MagicMock()
        mock_email.send_verification_email = AsyncMock(return_value=(200, "OK"))

        with patch("handlers.auth.get_db_safe", AsyncMock(return_value=MagicMock())), \
             patch("handlers.auth.User", mock_user_cls), \
             patch("handlers.auth.EmailService", return_value=mock_email), \
             patch("handlers.auth.generate_jwt_token", return_value="fake.token"):
            resp = await handle_signup(MockRequest(body=body), MockEnv(), {}, {}, "/auth/signup")

        assert resp.status == 201

    @pytest.mark.asyncio
    async def test_username_exactly_150_chars_accepted(self):
        body = _valid_body(username="a" * 150)
        mock_user_cls = MagicMock()
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.first = AsyncMock(return_value=None)
        mock_user_cls.objects.return_value = mock_qs
        mock_user_cls.create = AsyncMock(return_value={"id": 1})

        mock_email = MagicMock()
        mock_email.send_verification_email = AsyncMock(return_value=(200, "OK"))

        with patch("handlers.auth.get_db_safe", AsyncMock(return_value=MagicMock())), \
             patch("handlers.auth.User", mock_user_cls), \
             patch("handlers.auth.EmailService", return_value=mock_email), \
             patch("handlers.auth.generate_jwt_token", return_value="fake.token"):
            resp = await handle_signup(MockRequest(body=body), MockEnv(), {}, {}, "/auth/signup")

        assert resp.status == 201

    @pytest.mark.asyncio
    async def test_username_non_string_returns_400(self):
        body = _valid_body(username=12345)
        resp = await handle_signup(MockRequest(body=body), MockEnv(), {}, {}, "/auth/signup")
        assert resp.status == 400


# ─── Email validation ───────────────────────────────────────────────────


class TestEmailValidation:
    @pytest.mark.asyncio
    async def test_email_without_at_returns_400(self):
        body = _valid_body(email="notanemail")
        resp = await handle_signup(MockRequest(body=body), MockEnv(), {}, {}, "/auth/signup")
        assert resp.status == 400
        data = resp.data if isinstance(resp.data, dict) else json.loads(resp.body)
        assert "email" in data.get("message", "").lower()

    @pytest.mark.asyncio
    async def test_email_without_domain_returns_400(self):
        body = _valid_body(email="user@")
        resp = await handle_signup(MockRequest(body=body), MockEnv(), {}, {}, "/auth/signup")
        assert resp.status == 400

    @pytest.mark.asyncio
    async def test_email_without_tld_returns_400(self):
        body = _valid_body(email="user@domain")
        resp = await handle_signup(MockRequest(body=body), MockEnv(), {}, {}, "/auth/signup")
        assert resp.status == 400

    @pytest.mark.asyncio
    async def test_email_with_spaces_returns_400(self):
        body = _valid_body(email="user @example.com")
        resp = await handle_signup(MockRequest(body=body), MockEnv(), {}, {}, "/auth/signup")
        assert resp.status == 400

    @pytest.mark.asyncio
    async def test_valid_email_accepted(self):
        body = _valid_body(email="user.name+tag@sub.example.com")
        mock_user_cls = MagicMock()
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.first = AsyncMock(return_value=None)
        mock_user_cls.objects.return_value = mock_qs
        mock_user_cls.create = AsyncMock(return_value={"id": 1})

        mock_email = MagicMock()
        mock_email.send_verification_email = AsyncMock(return_value=(200, "OK"))

        with patch("handlers.auth.get_db_safe", AsyncMock(return_value=MagicMock())), \
             patch("handlers.auth.User", mock_user_cls), \
             patch("handlers.auth.EmailService", return_value=mock_email), \
             patch("handlers.auth.generate_jwt_token", return_value="fake.token"):
            resp = await handle_signup(MockRequest(body=body), MockEnv(), {}, {}, "/auth/signup")

        assert resp.status == 201

    @pytest.mark.asyncio
    async def test_email_non_string_returns_400(self):
        body = _valid_body(email=12345)
        resp = await handle_signup(MockRequest(body=body), MockEnv(), {}, {}, "/auth/signup")
        assert resp.status == 400


# ─── Password validation ────────────────────────────────────────────────


class TestPasswordValidation:
    @pytest.mark.asyncio
    async def test_password_too_short_returns_400(self):
        body = _valid_body(password="short")
        resp = await handle_signup(MockRequest(body=body), MockEnv(), {}, {}, "/auth/signup")
        assert resp.status == 400
        data = resp.data if isinstance(resp.data, dict) else json.loads(resp.body)
        assert "8 characters" in data.get("message", "")

    @pytest.mark.asyncio
    async def test_password_exactly_7_chars_returns_400(self):
        body = _valid_body(password="1234567")
        resp = await handle_signup(MockRequest(body=body), MockEnv(), {}, {}, "/auth/signup")
        assert resp.status == 400

    @pytest.mark.asyncio
    async def test_password_exactly_8_chars_accepted(self):
        body = _valid_body(password="12345678")
        mock_user_cls = MagicMock()
        mock_qs = MagicMock()
        mock_qs.filter.return_value = mock_qs
        mock_qs.first = AsyncMock(return_value=None)
        mock_user_cls.objects.return_value = mock_qs
        mock_user_cls.create = AsyncMock(return_value={"id": 1})

        mock_email = MagicMock()
        mock_email.send_verification_email = AsyncMock(return_value=(200, "OK"))

        with patch("handlers.auth.get_db_safe", AsyncMock(return_value=MagicMock())), \
             patch("handlers.auth.User", mock_user_cls), \
             patch("handlers.auth.EmailService", return_value=mock_email), \
             patch("handlers.auth.generate_jwt_token", return_value="fake.token"):
            resp = await handle_signup(MockRequest(body=body), MockEnv(), {}, {}, "/auth/signup")

        assert resp.status == 201

    @pytest.mark.asyncio
    async def test_single_char_password_returns_400(self):
        body = _valid_body(password="a")
        resp = await handle_signup(MockRequest(body=body), MockEnv(), {}, {}, "/auth/signup")
        assert resp.status == 400

    @pytest.mark.asyncio
    async def test_empty_password_returns_400(self):
        body = _valid_body(password="")
        resp = await handle_signup(MockRequest(body=body), MockEnv(), {}, {}, "/auth/signup")
        assert resp.status == 400

    @pytest.mark.asyncio
    async def test_password_non_string_returns_400(self):
        body = _valid_body(password=12345678)
        resp = await handle_signup(MockRequest(body=body), MockEnv(), {}, {}, "/auth/signup")
        assert resp.status == 400

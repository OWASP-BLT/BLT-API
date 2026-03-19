"""
Tests for the organizations handler (src/handlers/organizations.py).

Uses the same lightweight MockDB pattern as test_orm.py — no real
database or HTTP server required.
"""

import pytest
import sys
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from handlers.organizations import handle_organizations, ALLOWED_ORG_TYPES


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

class MockDB:
    """Minimal async mock for Cloudflare D1 database binding."""
    def __init__(self):
        self._last_sql = None
        self._last_params = None
        self._all_sql_calls = []
        self._all_return = _MockAllResult([])
        self._first_return = None

    def prepare(self, sql):
        return _FakeStatement(self, sql)


class _FakeStatement:
    def __init__(self, db, sql):
        self._db = db
        self._sql = sql
        self._params = ()

    def bind(self, *params):
        self._params = params
        return self

    async def all(self):
        self._db._last_sql = self._sql
        self._db._last_params = self._params
        self._db._all_sql_calls.append(self._sql)
        return self._db._all_return

    async def first(self):
        self._db._last_sql = self._sql
        self._db._last_params = self._params
        self._db._all_sql_calls.append(self._sql)
        return self._db._first_return

    async def run(self):
        self._db._last_sql = self._sql
        self._db._last_params = self._params
        self._db._all_sql_calls.append(self._sql)


class _MockAllResult:
    def __init__(self, rows):
        self.results = rows


def make_env(db):
    env = MagicMock()
    env.DB = db
    return env


def make_request():
    req = MagicMock()
    req.method = "GET"
    return req


def make_response_json(data):
    """Simulate Response.json() returning a dict."""
    resp = MagicMock()
    resp._data = data
    return resp


# ---------------------------------------------------------------------------
# ALLOWED_ORG_TYPES
# ---------------------------------------------------------------------------

class TestAllowedOrgTypes:
    def test_contains_expected_types(self):
        assert "company" in ALLOWED_ORG_TYPES
        assert "nonprofit" in ALLOWED_ORG_TYPES
        assert "education" in ALLOWED_ORG_TYPES

    def test_does_not_contain_invalid(self):
        assert "invalid" not in ALLOWED_ORG_TYPES
        assert "government" not in ALLOWED_ORG_TYPES


# ---------------------------------------------------------------------------
# Input Validation
# ---------------------------------------------------------------------------

class TestOrganizationInputValidation:
    @pytest.mark.asyncio
    async def test_invalid_org_id_returns_400(self):
        db = MockDB()
        with patch("handlers.organizations.get_db_safe", AsyncMock(return_value=db)):
            response = await handle_organizations(
                make_request(), make_env(db),
                path_params={"id": "abc"},
                query_params={},
                path="/organizations/abc"
            )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_invalid_is_active_returns_400(self):
        db = MockDB()
        db._all_return = _MockAllResult([])
        db._first_return = MagicMock(to_py=lambda: {"total": 0})
        with patch("handlers.organizations.get_db_safe", AsyncMock(return_value=db)):
            response = await handle_organizations(
                make_request(), make_env(db),
                path_params={},
                query_params={"is_active": "maybe"},
                path="/organizations"
            )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_invalid_org_type_returns_400(self):
        db = MockDB()
        db._all_return = _MockAllResult([])
        db._first_return = MagicMock(to_py=lambda: {"total": 0})
        with patch("handlers.organizations.get_db_safe", AsyncMock(return_value=db)):
            response = await handle_organizations(
                make_request(), make_env(db),
                path_params={},
                query_params={"type": "government"},
                path="/organizations"
            )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_valid_is_active_true_accepted(self):
        db = MockDB()
        db._all_return = _MockAllResult([])
        db._first_return = MagicMock(to_py=lambda: {"total": 0})
        with patch("handlers.organizations.get_db_safe", AsyncMock(return_value=db)):
            response = await handle_organizations(
                make_request(), make_env(db),
                path_params={},
                query_params={"is_active": "true"},
                path="/organizations"
            )
        assert response.status_code != 400

    @pytest.mark.asyncio
    async def test_valid_org_type_accepted(self):
        db = MockDB()
        db._all_return = _MockAllResult([])
        db._first_return = MagicMock(to_py=lambda: {"total": 0})
        with patch("handlers.organizations.get_db_safe", AsyncMock(return_value=db)):
            response = await handle_organizations(
                make_request(), make_env(db),
                path_params={},
                query_params={"type": "company"},
                path="/organizations"
            )
        assert response.status_code != 400


# ---------------------------------------------------------------------------
# DB connection failure
# ---------------------------------------------------------------------------

class TestDBConnectionFailure:
    @pytest.mark.asyncio
    async def test_db_failure_returns_503(self):
        with patch("handlers.organizations.get_db_safe",
                   AsyncMock(side_effect=Exception("DB unavailable"))):
            response = await handle_organizations(
                make_request(), make_env(None),
                path_params={},
                query_params={},
                path="/organizations"
            )
        assert response.status_code == 503

    @pytest.mark.asyncio
    async def test_503_does_not_leak_error_message(self):
        with patch("handlers.organizations.get_db_safe",
                   AsyncMock(side_effect=Exception("secret connection string"))):
            response = await handle_organizations(
                make_request(), make_env(None),
                path_params={},
                query_params={},
                path="/organizations"
            )
        body = response.body if hasattr(response, "body") else str(response)
        assert "secret connection string" not in body


# ---------------------------------------------------------------------------
# include token normalization
# ---------------------------------------------------------------------------

class TestIncludeTokenNormalization:
    def test_include_tokens_lowercase(self):
        """Ensure include tokens are normalized to lowercase."""
        tokens = [i.strip().lower() for i in "Managers, Tags, STATS".split(",")]
        assert tokens == ["managers", "tags", "stats"]

    def test_include_tokens_strip_whitespace(self):
        tokens = [i.strip().lower() for i in "managers, tags".split(",")]
        assert "tags" in tokens
        assert " tags" not in tokens


# ---------------------------------------------------------------------------
# _get_organization_stats helper
# ---------------------------------------------------------------------------

class TestGetOrganizationStats:
    @pytest.mark.asyncio
    async def test_stats_returns_all_four_keys(self):
        from handlers.organizations import _get_organization_stats
        db = MockDB()
        db._first_return = MagicMock(to_py=lambda: {"total": 5})
        stats = await _get_organization_stats(db, 1)
        assert "domain_count" in stats
        assert "bug_count" in stats
        assert "verified_bug_count" in stats
        assert "manager_count" in stats

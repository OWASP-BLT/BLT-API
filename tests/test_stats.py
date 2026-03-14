"""
Tests for the stats handler.
"""

import importlib.util
import json
import pytest
import sys
from pathlib import Path

SRC_PATH = Path(__file__).resolve().parent.parent / "src"
sys.path.insert(0, str(SRC_PATH))
# Importing handlers.stats via package triggers handlers/__init__.py, which imports
# workers-dependent modules not available in this isolated test environment.
stats_spec = importlib.util.spec_from_file_location(
    "stats_handler_module",
    SRC_PATH / "handlers" / "stats.py",
)
stats_handler = importlib.util.module_from_spec(stats_spec)
stats_spec.loader.exec_module(stats_handler)


class MockRequest:
    """Mock request object for testing."""

    method = "GET"


class MockEnv:
    """Mock environment object for testing."""

    pass


class FakeQuerySet:
    """Minimal queryset stub for count-based handler tests."""

    def __init__(self, counts, filters=None, error=None):
        self._counts = counts
        self._filters = filters or {}
        self._error = error

    def filter(self, **kwargs):
        next_filters = dict(self._filters)
        next_filters.update(kwargs)
        return FakeQuerySet(self._counts, filters=next_filters, error=self._error)

    async def count(self):
        if self._error is not None:
            raise self._error
        key = tuple(sorted(self._filters.items()))
        return self._counts.get(key, 0)


class FakeModel:
    """Model stub exposing the objects(db) API used by the handler."""

    def __init__(self, counts, error=None):
        self._counts = counts
        self._error = error

    def objects(self, db):
        return FakeQuerySet(self._counts, error=self._error)


def parse_response(response):
    """Decode a mocked JSON response body into a Python object."""

    return json.loads(response.body)


class TestStatsHandler:
    """Tests for the /stats handler."""

    @pytest.mark.asyncio
    async def test_stats_returns_backward_compatible_counts(self, monkeypatch):
        async def fake_get_db_safe(env):
            return object()

        monkeypatch.setattr(stats_handler, "get_db_safe", fake_get_db_safe)
        monkeypatch.setattr(
            stats_handler,
            "Bug",
            FakeModel({(): 8, (("status", "open"),): 3, (("status", "closed"),): 4}),
        )
        monkeypatch.setattr(stats_handler, "User", FakeModel({(("is_active", 1),): 5}))
        monkeypatch.setattr(stats_handler, "Domain", FakeModel({(("is_active", 1),): 2}))

        response = await stats_handler.handle_stats(
            MockRequest(),
            MockEnv(),
            path_params={},
            query_params={},
            path="/stats",
        )

        payload = parse_response(response)

        assert response.status == 200
        assert payload["success"] is True
        assert payload["data"] == {
            "bugs": 8,
            "bugs_breakdown": {
                "total": 8,
                "open": 3,
                "closed": 4,
                "other": 1,
            },
            "users": 5,
            "active_users": 5,
            "domains": 2,
            "active_domains": 2,
        }
        assert payload["description"]["users"] == "Total number of active registered users"
        assert payload["description"]["domains"] == "Total number of active tracked domains"

    @pytest.mark.asyncio
    async def test_stats_returns_error_when_db_connection_fails(self, monkeypatch):
        async def fake_get_db_safe(env):
            raise RuntimeError("db unavailable")

        monkeypatch.setattr(stats_handler, "get_db_safe", fake_get_db_safe)

        response = await stats_handler.handle_stats(
            MockRequest(),
            MockEnv(),
            path_params={},
            query_params={},
            path="/stats",
        )

        payload = parse_response(response)

        assert response.status == 500
        assert payload["error"] is True
        assert payload["status"] == 500
        assert payload["message"] == "Database connection error: db unavailable"

    @pytest.mark.asyncio
    async def test_stats_returns_error_when_count_query_fails(self, monkeypatch):
        async def fake_get_db_safe(env):
            return object()

        monkeypatch.setattr(stats_handler, "get_db_safe", fake_get_db_safe)
        monkeypatch.setattr(stats_handler, "Bug", FakeModel({}, error=RuntimeError("count failed")))
        monkeypatch.setattr(stats_handler, "User", FakeModel({(("is_active", 1),): 5}))
        monkeypatch.setattr(stats_handler, "Domain", FakeModel({(("is_active", 1),): 2}))

        response = await stats_handler.handle_stats(
            MockRequest(),
            MockEnv(),
            path_params={},
            query_params={},
            path="/stats",
        )

        payload = parse_response(response)

        assert response.status == 500
        assert payload["error"] is True
        assert payload["status"] == 500
        assert payload["message"] == "Error fetching stats: count failed"

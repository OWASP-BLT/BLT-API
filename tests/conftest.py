"""
Pytest configuration file to set up test environment.
"""

import sys
import types
from pathlib import Path

# Add src directory to Python path so imports work correctly
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

# Provide a lightweight `workers` module shim for tests that import handlers
# which depend on the Cloudflare Workers runtime.
import types as _types
if "workers" not in sys.modules:
    _workers_mod = _types.ModuleType("workers")

    class _Response:
        def __init__(self, body=None, status=200, headers=None):
            self.body = body
            self.status_code = status
            self.status = status
            self.headers = headers or {}

        @staticmethod
        def json(data, status=200, **kwargs):
            import json as _json
            r = _Response(_json.dumps(data), status, kwargs.get("headers"))
            return r

        @staticmethod
        def new(body=None, status=200, headers=None):
            return _Response(body, status, headers)

    _workers_mod.Response = _Response
    _workers_mod.WorkerEntrypoint = type("WorkerEntrypoint", (), {})
    sys.modules["workers"] = _workers_mod

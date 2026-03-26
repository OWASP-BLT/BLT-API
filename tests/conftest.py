"""
Pytest configuration file to set up test environment.
"""

import json
import sys
import types
from pathlib import Path

# Add src directory to Python path so imports work correctly
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))


# Provide a lightweight `workers` module for local/CI test runs where the
# Cloudflare runtime package is unavailable.
if "workers" not in sys.modules:
	workers_mod = types.ModuleType("workers")

	class WorkerEntrypoint:  # pragma: no cover - shim for imports only
		pass

	class _WorkersResponse:  # pragma: no cover - shim for imports only
		def __init__(self, data=None, status=200, headers=None, body=None):
			self.data = data
			self.status = status
			self.headers = headers or {}
			self.body = body

	class Response:  # pragma: no cover - shim for imports only
		@staticmethod
		def json(data, status=200, headers=None):
			return _WorkersResponse(data=data, status=status, headers=headers or {}, body=json.dumps(data))

		@staticmethod
		def new(body=None, status=200, headers=None):
			try:
				data = json.loads(body) if body else None
			except (TypeError, ValueError):
				data = None
			return _WorkersResponse(data=data, status=status, headers=headers or {}, body=body)

	setattr(workers_mod, "WorkerEntrypoint", WorkerEntrypoint)
	setattr(workers_mod, "Response", Response)
	sys.modules["workers"] = workers_mod

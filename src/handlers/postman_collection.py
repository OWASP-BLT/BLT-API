"""Postman collection download handler."""

from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable
from urllib.parse import urlencode

from utils import error_response, json_response


MAIN_FILE = Path(__file__).resolve().parents[1] / "main.py"
DEFAULT_RESPONSE_TIME_MS = 5000
LOGIN_ENDPOINT_ID = "post_auth_signin"
SIGNUP_ENDPOINT_ID = "post_auth_signup"


@dataclass(frozen=True)
class EndpointDefinition:
    endpoint_id: str
    method: str
    path: str
    expected_status: int
    query_params: tuple[tuple[str, str], ...] = ()
    body: dict[str, Any] | None = None

    @property
    def display_name(self) -> str:
        return f"{self.method} {self.path}"


EXPECTED_STATUS_OVERRIDES = {
    ("POST", "/auth/signup"): 201,
    ("POST", "/bugs"): 201,
}

QUERY_PARAM_SAMPLES = {
    ("GET", "/bugs"): (("page", "1"), ("per_page", "20")),
    ("GET", "/bugs/search"): (("q", "sql injection"), ("limit", "10")),
    ("GET", "/auth/verify-email"): (("token", "sample-verification-token"),),
}

BODY_SAMPLES = {
    ("POST", "/auth/signin"): {
        "username": "{{username}}",
        "password": "{{password}}",
    },
    ("POST", "/auth/signup"): {
        "username": "{{signup_username}}",
        "email": "{{signup_email}}",
        "password": "{{signup_password}}",
    },
    ("POST", "/bugs"): {
        "url": "https://example.com/vulnerability",
        "description": "Bug report created from generated Postman collection endpoint.",
        "status": "open",
    },
}


def build_endpoint_id(method: str, path: str) -> str:
    normalized_path = re.sub(r"[^a-z0-9]+", "_", path.lower()).strip("_")
    return f"{method.lower()}_{normalized_path or 'root'}"


def substitute_path_params(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "1", path)


def discover_routes(main_file: Path = MAIN_FILE) -> list[EndpointDefinition]:
    tree = ast.parse(main_file.read_text(encoding="utf-8"), filename=str(main_file))
    routes: list[EndpointDefinition] = []

    def iter_nodes_in_source_order(node: ast.AST) -> Iterable[ast.AST]:
        for child in ast.iter_child_nodes(node):
            yield child
            yield from iter_nodes_in_source_order(child)

    for statement in tree.body:
        for node in iter_nodes_in_source_order(statement):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr != "add_route":
                continue
            if not isinstance(node.func.value, ast.Name) or node.func.value.id != "router":
                continue
            if len(node.args) < 3:
                continue

            method_node, path_node = node.args[:2]
            if not isinstance(method_node, ast.Constant) or not isinstance(method_node.value, str):
                continue
            if not isinstance(path_node, ast.Constant) or not isinstance(path_node.value, str):
                continue

            method = method_node.value.upper()
            path = path_node.value
            if path == "/":
                continue

            routes.append(
                EndpointDefinition(
                    endpoint_id=build_endpoint_id(method, path),
                    method=method,
                    path=path,
                    expected_status=EXPECTED_STATUS_OVERRIDES.get((method, path), 200),
                    query_params=QUERY_PARAM_SAMPLES.get((method, path), ()),
                    body=BODY_SAMPLES.get((method, path)),
                )
            )

    return routes


def reorder_endpoints(endpoints: list[EndpointDefinition]) -> list[EndpointDefinition]:
    endpoint_map = {endpoint.endpoint_id: endpoint for endpoint in endpoints}
    if LOGIN_ENDPOINT_ID not in endpoint_map:
        return endpoints

    ordered: list[EndpointDefinition] = [endpoint_map[LOGIN_ENDPOINT_ID]]
    ordered.extend(
        endpoint for endpoint in endpoints if endpoint.endpoint_id != LOGIN_ENDPOINT_ID
    )
    return ordered


def build_postman_tests(endpoint: EndpointDefinition, response_time_ms: int) -> str:
    lines = [
        f'pm.test("Status code is {endpoint.expected_status}", function () {{',
        f"    pm.response.to.have.status({endpoint.expected_status});",
        "});",
        "",
        f'pm.test("Response time is below {response_time_ms}ms", function () {{',
        f"    pm.expect(pm.response.responseTime).to.be.below({response_time_ms});",
        "});",
        "",
        "let responseJson = null;",
        'pm.test("Response body is valid JSON", function () {',
        "    pm.expect(function () {",
        "        responseJson = pm.response.json();",
        "    }).to.not.throw();",
        "    pm.expect(responseJson).to.not.equal(null);",
        '    pm.expect(typeof responseJson).to.eql("object");',
        "});",
    ]

    if endpoint.endpoint_id == LOGIN_ENDPOINT_ID:
        lines.extend(
            [
                "",
                'pm.test("Authentication token is present", function () {',
                '    pm.expect(responseJson).to.have.property("token");',
                '    pm.expect(responseJson.token).to.be.a("string").and.not.empty;',
                '    pm.environment.set("token", responseJson.token);',
                "});",
            ]
        )

    return "\n".join(lines)


def build_prerequest_script(endpoint: EndpointDefinition) -> str | None:
    if endpoint.endpoint_id != SIGNUP_ENDPOINT_ID:
        return None

    return "\n".join(
        [
            'const baseUsername = pm.environment.get("username");',
            'const basePassword = pm.environment.get("password");',
            "",
            'pm.test("Signup source credentials are configured", function () {',
            '    pm.expect(baseUsername).to.be.a("string").and.not.empty;',
            '    pm.expect(basePassword).to.be.a("string").and.not.empty;',
            "});",
            "",
            "const signupRunId = Date.now().toString();",
            'pm.collectionVariables.set("signup_username", `${baseUsername}_signup_${signupRunId}`);',
            'pm.collectionVariables.set("signup_password", `${basePassword}_signup`);',
            'pm.collectionVariables.set("signup_email", `${baseUsername}_signup_${signupRunId}@example.com`);',
        ]
    )


def build_url(endpoint: EndpointDefinition) -> str:
    path = substitute_path_params(endpoint.path)
    raw_url = f"{{{{base_url}}}}{path}"
    if endpoint.query_params:
        raw_url = f"{raw_url}?{urlencode(endpoint.query_params)}"
    return raw_url


def build_request_item(endpoint: EndpointDefinition, response_time_ms: int) -> dict[str, Any]:
    headers = [{"key": "Accept", "value": "application/json"}]
    if endpoint.endpoint_id != LOGIN_ENDPOINT_ID:
        headers.append({"key": "Authorization", "value": "Token {{token}}"})
    if endpoint.body is not None:
        headers.append({"key": "Content-Type", "value": "application/json"})

    request: dict[str, Any] = {
        "method": endpoint.method,
        "header": headers,
        "url": build_url(endpoint),
        "description": f"Generated from {endpoint.method} {endpoint.path}",
    }

    if endpoint.body is not None:
        request["body"] = {
            "mode": "raw",
            "raw": json.dumps(endpoint.body, indent=2),
            "options": {"raw": {"language": "json"}},
        }

    events = []
    prerequest_script = build_prerequest_script(endpoint)
    if prerequest_script is not None:
        events.append(
            {
                "listen": "prerequest",
                "script": {
                    "type": "text/javascript",
                    "exec": prerequest_script.splitlines(),
                },
            }
        )

    events.append(
        {
            "listen": "test",
            "script": {
                "type": "text/javascript",
                "exec": build_postman_tests(endpoint, response_time_ms).splitlines(),
            },
        }
    )

    return {
        "name": endpoint.display_name,
        "event": events,
        "request": request,
        "response": [],
    }


def build_collection(response_time_ms: int = DEFAULT_RESPONSE_TIME_MS) -> dict[str, Any]:
    endpoints = reorder_endpoints(discover_routes())

    return {
        "info": {
            "name": "BLT API",
            "description": "Generated Postman Collection v2.1 for the BLT API.",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": [build_request_item(endpoint, response_time_ms) for endpoint in endpoints],
    }


async def handle_postman_collection(
    request: Any,
    env: Any,
    path_params: Dict[str, str],
    query_params: Dict[str, str],
    path: str,
) -> Any:
    """Return a generated Postman collection JSON payload.

    Query params:
    - response_time_ms: optional positive integer used in generated Postman tests.
    """
    del request, env, path_params, path

    response_time_ms = DEFAULT_RESPONSE_TIME_MS
    raw_response_time_ms = query_params.get("response_time_ms")

    if raw_response_time_ms is not None:
        try:
            response_time_ms = int(raw_response_time_ms)
            if response_time_ms <= 0:
                raise ValueError
        except ValueError:
            return error_response(
                message="Invalid response_time_ms. Expected a positive integer.",
                status=400,
            )

    collection = build_collection(response_time_ms=response_time_ms)

    return json_response(
        collection,
        headers={
            "Content-Disposition": 'attachment; filename="blt_api_postman_collection.json"'
        },
    )
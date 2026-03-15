#!/usr/bin/env python3
"""
generate_postman_collection.py
==============================
Generates a Postman Collection v2.1 for the BLT API project.

The script parses ``src/main.py`` using the Python ``ast`` module to discover
every registered route and turns each one into a Postman request item. No
running server is required.


Quick start
-----------
::

    # Default: write blt_api_postman_collection.json to the project root
    python scripts/generate_postman_collection.py

    # Write to a custom path
    python scripts/generate_postman_collection.py --output ~/Desktop/blt.json

    # Print all discovered endpoint ids and exit (useful for --order)
    python scripts/generate_postman_collection.py --list-endpoints

    # Specify explicit execution order (login must be first)
    python scripts/generate_postman_collection.py \\
        --order post_auth_signin get_health get_bugs get_bugs_id

    # Adjust the response-time threshold used in Postman tests
    python scripts/generate_postman_collection.py --response-time-ms 3000


CLI arguments
-------------
--output PATH
    Destination file for the generated collection JSON.
    Defaults to ``<project-root>/blt_api_postman_collection.json``.

--order ID [ID ...]
    Whitespace-separated list of endpoint ids that should appear **first** in
    the collection, in the given order. The first id **must** be
    ``post_auth_signin``. Any endpoints not listed are appended afterwards in
    their original discovery order. Use ``--list-endpoints`` to see all valid
    ids.

--response-time-ms MS
    Upper bound (in milliseconds) for the ``Response time`` Postman test that
    is added to every request. Defaults to ``5000``.

--list-endpoints
    Print ``<endpoint_id>: METHOD /path`` for every discovered route and exit.
    Nothing is written to disk.


Authentication flow
-------------------
1. The first request in the collection is always ``POST /auth/signin``.
2. Its body uses the ``{{username}}`` and ``{{password}}`` environment
   variables so you never have to hard-code credentials.
3. The test script for that request extracts ``response.token`` and stores it
   via ``pm.environment.set("token", ...)``.
4. Every other request automatically includes the header::

       Authorization: Bearer {{token}}


Required Postman environment variables
--------------------------------------
Create a Postman environment and set the four variables below before running
the collection:

============  =======================================================
Variable      Description
============  =======================================================
base_url      Base URL of the API, e.g. ``http://localhost:8787``
username      Username of an existing active BLT account
password      Password for that account
token         Leave blank — populated automatically after sign-in
============  =======================================================


Per-request Postman tests
-------------------------
Every generated request has three built-in Postman tests:

* **Status code** — asserts the expected HTTP status (200, 201, …).
* **Response time** — asserts the response arrived within --response-time-ms ms.
* **Valid JSON** — parses the response body and asserts it is a non-null object.

The sign-in request additionally asserts that the ``token`` field is present and
non-empty in the response, and stores it in the environment.


How route discovery works
-------------------------
At generation time the script reads ``src/main.py`` through Python's ``ast``
module (no import, no code execution) and finds every call that matches::

    router.add_route("METHOD", "/path", handler_function)

The homepage route (``/``) is excluded because it returns HTML, not JSON.
All other routes produce a Postman request item with sensible defaults. Sample
request bodies and query parameters are provided for the following endpoints:

* ``POST /auth/signin`` — ``{"username": "{{username}}", "password": "{{password}}"}"
* ``POST /auth/signup`` — ``{"username", "email", "password"}``
* ``POST /bugs``        — ``{"url", "description", "status"}``
* ``GET  /bugs``        — ``?page=1&per_page=20``
* ``GET  /bugs/search`` — ``?q=sql+injection&limit=10``
* ``GET  /auth/verify-email`` — ``?token=sample-verification-token``


.. note::
    **Required parameters for endpoints without pre-filled samples**

    Endpoints not listed above are generated with an empty request body and no
    query parameters. Before running the collection in Postman you **must**
    manually open each such request and supply any required path parameters
    (e.g. replace the placeholder ``1`` in ``/bugs/1`` with a real id),
    query parameters, or body fields that the endpoint expects. Sending a
    request with missing required parameters will result in a ``400 Bad
    Request`` or ``404 Not Found`` response and failed Postman tests.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAIN_FILE = PROJECT_ROOT / "src" / "main.py"
DEFAULT_OUTPUT = PROJECT_ROOT / "blt_api_postman_collection.json"
LOGIN_ENDPOINT_ID = "post_auth_signin"
DEFAULT_RESPONSE_TIME_MS = 5000


@dataclass(frozen=True)
class EndpointDefinition:
    endpoint_id: str
    method: str
    path: str
    handler: str
    expected_status: int
    folder: str
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
        "username": "{{username}}",
        "email": "{{username}}@example.com",
        "password": "{{password}}",
    },
    ("POST", "/bugs"): {
        "url": "https://example.com/vulnerability",
        "description": "Bug report created from the generated Postman collection.",
        "status": "open",
    },
}


def build_endpoint_id(method: str, path: str) -> str:
    normalized_path = re.sub(r"[^a-z0-9]+", "_", path.lower()).strip("_")
    return f"{method.lower()}_{normalized_path or 'root'}"


def classify_folder(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    if not parts:
        return "Misc"
    return parts[0].replace("-", " ").title()


def substitute_path_params(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "1", path)


def discover_routes(main_file: Path = MAIN_FILE) -> list[EndpointDefinition]:
    tree = ast.parse(main_file.read_text(), filename=str(main_file))
    routes: list[EndpointDefinition] = []

    for node in ast.walk(tree):
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

        method_node, path_node, handler_node = node.args[:3]
        if not isinstance(method_node, ast.Constant) or not isinstance(method_node.value, str):
            continue
        if not isinstance(path_node, ast.Constant) or not isinstance(path_node.value, str):
            continue
        if not isinstance(handler_node, ast.Name):
            continue

        method = method_node.value.upper()
        path = path_node.value
        handler = handler_node.id

        if path == "/" or handler == "handle_homepage":
            continue

        routes.append(
            EndpointDefinition(
                endpoint_id=build_endpoint_id(method, path),
                method=method,
                path=path,
                handler=handler,
                expected_status=EXPECTED_STATUS_OVERRIDES.get((method, path), 200),
                folder=classify_folder(path),
                query_params=QUERY_PARAM_SAMPLES.get((method, path), ()),
                body=BODY_SAMPLES.get((method, path)),
            )
        )

    return routes


def reorder_endpoints(
    endpoints: Iterable[EndpointDefinition],
    ordered_ids: list[str] | None = None,
) -> list[EndpointDefinition]:
    discovered = list(endpoints)
    endpoint_map = {endpoint.endpoint_id: endpoint for endpoint in discovered}

    if LOGIN_ENDPOINT_ID not in endpoint_map:
        raise ValueError("The login endpoint POST /auth/signin was not discovered.")

    if ordered_ids:
        unknown_ids = [endpoint_id for endpoint_id in ordered_ids if endpoint_id not in endpoint_map]
        if unknown_ids:
            available = ", ".join(sorted(endpoint_map))
            raise ValueError(
                f"Unknown endpoint ids: {', '.join(unknown_ids)}. Available ids: {available}"
            )
        if ordered_ids[0] != LOGIN_ENDPOINT_ID:
            raise ValueError(
                f"The first endpoint must be {LOGIN_ENDPOINT_ID} to satisfy the auth flow."
            )
        deduped_order = list(dict.fromkeys(ordered_ids))
    else:
        deduped_order = [LOGIN_ENDPOINT_ID]

    remaining = [
        endpoint.endpoint_id
        for endpoint in discovered
        if endpoint.endpoint_id not in deduped_order
    ]
    final_order = deduped_order + remaining
    return [endpoint_map[endpoint_id] for endpoint_id in final_order]


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
        'let responseJson = null;',
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


def build_url(endpoint: EndpointDefinition) -> str:
    path = substitute_path_params(endpoint.path)
    raw_url = f"{{{{base_url}}}}{path}"
    if endpoint.query_params:
        query_string = "&".join(f"{key}={value}" for key, value in endpoint.query_params)
        raw_url = f"{raw_url}?{query_string}"
    return raw_url


def build_request_item(endpoint: EndpointDefinition, response_time_ms: int) -> dict[str, Any]:
    headers = [{"key": "Accept", "value": "application/json"}]
    if endpoint.endpoint_id != LOGIN_ENDPOINT_ID:
        headers.append({"key": "Authorization", "value": "Bearer {{token}}"})
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

    return {
        "name": endpoint.display_name,
        "event": [
            {
                "listen": "test",
                "script": {
                    "type": "text/javascript",
                    "exec": build_postman_tests(endpoint, response_time_ms).splitlines(),
                },
            }
        ],
        "request": request,
        "response": [],
    }


def build_items(endpoints: Iterable[EndpointDefinition], response_time_ms: int) -> list[dict[str, Any]]:
    return [
        build_request_item(endpoint, response_time_ms)
        for endpoint in endpoints
    ]


def build_collection(
    ordered_ids: list[str] | None = None,
    response_time_ms: int = DEFAULT_RESPONSE_TIME_MS,
) -> dict[str, Any]:
    routes = discover_routes()
    ordered_endpoints = reorder_endpoints(routes, ordered_ids)

    description = "\n".join(
        [
            "Generated Postman Collection v2.1 for the BLT API.",
            "Required Postman environment variables:",
            "- base_url",
            "- username",
            "- password",
            "- token",
            f"The first request is {LOGIN_ENDPOINT_ID} and stores the JWT in pm.environment.set(\"token\", value).",
        ]
    )

    return {
        "info": {
            "name": "BLT API",
            "description": description,
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": build_items(ordered_endpoints, response_time_ms),
    }


def save_collection(output_path: Path, collection: dict[str, Any]) -> None:
    output_path.write_text(json.dumps(collection, indent=2) + "\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a Postman Collection v2.1 for the BLT API."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Output collection path. Defaults to {DEFAULT_OUTPUT.name} in the project root.",
    )
    parser.add_argument(
        "--order",
        nargs="*",
        default=None,
        help=(
            "Optional endpoint ids to prioritize. The first id must be "
            f"{LOGIN_ENDPOINT_ID}. Use --list-endpoints to inspect valid ids."
        ),
    )
    parser.add_argument(
        "--response-time-ms",
        type=int,
        default=DEFAULT_RESPONSE_TIME_MS,
        help="Maximum allowed response time for generated Postman tests.",
    )
    parser.add_argument(
        "--list-endpoints",
        action="store_true",
        help="Print discovered endpoint ids and exit.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    endpoints = discover_routes()

    if args.list_endpoints:
        for endpoint in endpoints:
            print(f"{endpoint.endpoint_id}: {endpoint.method} {endpoint.path}")
        return 0

    collection = build_collection(args.order, args.response_time_ms)
    save_collection(args.output, collection)
    print(f"Saved Postman collection to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
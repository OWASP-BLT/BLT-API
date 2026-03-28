"""
Repositories handler for the BLT API.
"""

import logging
from typing import Any, Dict
from utils import json_response, error_response, paginated_response, parse_pagination_params, client_call
from client import create_client


logger = logging.getLogger(__name__)


async def handle_repos(
    request: Any,
    env: Any,
    path_params: Dict[str, str],
    query_params: Dict[str, str],
    path: str
) -> Any:
    """
    Handle repository-related requests.

    Endpoints:
        GET /repos - List repositories with pagination
        GET /repos/{id} - Get a specific repository
    """
    try:
        client = create_client(env)
    except Exception as e:
        logger.error("Failed to initialize client in repos: %s", str(e))
        return error_response("Service Unavailable", status=503)

    if "id" in path_params:
        repo_id = path_params["id"]

        if not repo_id.isdigit():
            return error_response("Invalid repository ID", status=400)

        return json_response({
            "success": True,
            "message": "Repository details endpoint",
            "data": {
                "id": int(repo_id),
                "note": "Direct repository lookup may require organization context"
            }
        })

    page, per_page = parse_pagination_params(query_params)
    org_id = query_params.get("organization")

    if org_id and org_id.isdigit():
        result, err = await client_call(client.get_organization_repos(int(org_id), page=page, per_page=per_page), logger, "repos")
        if err:
            return err
        if result.get("error"):
            return error_response(result.get("message", "Failed to fetch repositories"), status=result.get("status", 500))
        data = result.get("data", [])
        return json_response({
            "success": True,
            "organization_id": int(org_id),
            "data": data,
            "count": len(data) if isinstance(data, list) else 0
        })

    return json_response({
        "success": True,
        "message": "Repository listing",
        "info": "Use ?organization={id} to get repositories for a specific organization",
        "endpoints": {
            "organization_repos": "/organizations/{id}/repos",
            "project_repos": "/projects/{id}/repos"
        }
    })

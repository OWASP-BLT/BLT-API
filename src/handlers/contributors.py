"""
Contributors handler for the BLT API.
"""

import logging
from typing import Any, Dict
from utils import json_response, error_response, paginated_response, parse_pagination_params, client_call
from client import create_client


logger = logging.getLogger(__name__)


async def handle_contributors(
    request: Any,
    env: Any,
    path_params: Dict[str, str],
    query_params: Dict[str, str],
    path: str
) -> Any:
    """
    Handle contributor-related requests.

    Endpoints:
        GET /contributors - List contributors with pagination
        GET /contributors/{id} - Get a specific contributor
    """
    try:
        client = create_client(env)
    except Exception as e:
        logger.error("Failed to initialize client in contributors: %s", str(e))
        return error_response("Service Unavailable", status=503)

    # Get specific contributor
    if "id" in path_params:
        contributor_id = path_params["id"]

        if not contributor_id.isdigit():
            return error_response("Invalid contributor ID", status=400)

        # NOTE: No dedicated get-by-ID endpoint; fetch with large per_page to reduce false 404s.
        # Contributors beyond this limit will not be found. Track improvement in a future issue.
        result, err = await client_call(client.get_contributors(per_page=200), logger, "contributors")
        if err:
            return err

        if result.get("error"):
            return error_response(
                result.get("message", "Contributor not found"),
                status=result.get("status", 404)
            )

        data = result.get("data", [])

        if isinstance(data, list):
            for contributor in data:
                if str(contributor.get("id")) == contributor_id or str(contributor.get("github_id")) == contributor_id:
                    return json_response({"success": True, "data": contributor})

        return error_response("Contributor not found", status=404)

    page, per_page = parse_pagination_params(query_params)

    result, err = await client_call(client.get_contributors(page=page, per_page=per_page), logger, "contributors")
    if err:
        return err

    if result.get("error"):
        return error_response(
            result.get("message", "Failed to fetch contributors"),
            status=result.get("status", 500)
        )

    data = result.get("data", {})

    if isinstance(data, dict) and "results" in data:
        return json_response({
            "success": True,
            "data": data.get("results", []),
            "pagination": {
                "page": page,
                "per_page": per_page,
                "count": len(data.get("results", [])),
                "total": data.get("count"),
                "next": data.get("next"),
                "previous": data.get("previous")
            }
        })

    if isinstance(data, list):
        return paginated_response(data, page=page, per_page=per_page)

    return json_response({"success": True, "data": data})

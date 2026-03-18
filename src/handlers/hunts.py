"""
Bug Hunts handler for the BLT API.
"""

import logging
from typing import Any, Dict
from utils import json_response, error_response, paginated_response, parse_pagination_params
from client import create_client


logger = logging.getLogger(__name__)

async def handle_hunts(
    request: Any,
    env: Any,
    path_params: Dict[str, str],
    query_params: Dict[str, str],
    path: str
) -> Any:
    """
    Handle bug hunt-related requests.
    
    Endpoints:
        GET /hunts - List all bug hunts
        GET /hunts/{id} - Get a specific bug hunt
        GET /hunts/active - Get currently active hunts
        GET /hunts/previous - Get past hunts
        GET /hunts/upcoming - Get upcoming hunts
    """
    try:
        client = create_client(env)
    except Exception as e:
        logger.error("Failed to initialize client in hunts: %s", str(e))
        return error_response("Service Unavailable", status=503)

    # Get specific hunt
    if "id" in path_params:
        hunt_id = path_params["id"]
        
        # Validate ID is numeric
        if not hunt_id.isdigit():
            return error_response("Invalid hunt ID", status=400)
        
        try:
            result = await client.get_hunt(int(hunt_id))
        except Exception as e:
            logger.error("Request failed in hunts: %s", str(e))
            return error_response("Internal Server Error", status=500)
        
        if result.get("error"):
            return error_response(
                result.get("message", "Hunt not found"),
                status=result.get("status", 404)
            )
        
        return json_response({
            "success": True,
            "data": result.get("data")
        })
    
    # Get active hunts
    if path.endswith("/active"):
        try:
            result = await client.get_hunts(active=True)
        except Exception as e:
            logger.error("Request failed in hunts: %s", str(e))
            return error_response("Internal Server Error", status=500)
        
        if result.get("error"):
            return error_response(
                result.get("message", "Failed to fetch active hunts"),
                status=result.get("status", 500)
            )
        
        return json_response({
            "success": True,
            "filter": "active",
            "data": result.get("data", [])
        })
    
    # Get previous hunts
    if path.endswith("/previous"):
        try:
            result = await client.get_hunts(previous=True)
        except Exception as e:
            logger.error("Request failed in hunts: %s", str(e))
            return error_response("Internal Server Error", status=500)
        
        if result.get("error"):
            return error_response(
                result.get("message", "Failed to fetch previous hunts"),
                status=result.get("status", 500)
            )
        
        return json_response({
            "success": True,
            "filter": "previous",
            "data": result.get("data", [])
        })
    
    # Get upcoming hunts
    if path.endswith("/upcoming"):
        try:
            result = await client.get_hunts(upcoming=True)
        except Exception as e:
            logger.error("Request failed in hunts: %s", str(e))
            return error_response("Internal Server Error", status=500)
        
        if result.get("error"):
            return error_response(
                result.get("message", "Failed to fetch upcoming hunts"),
                status=result.get("status", 500)
            )
        
        return json_response({
            "success": True,
            "filter": "upcoming",
            "data": result.get("data", [])
        })
    
    # List all hunts with pagination
    page, per_page = parse_pagination_params(query_params)
    
    # Check for filter params
    active = query_params.get("active") == "true"
    previous = query_params.get("previous") == "true"
    upcoming = query_params.get("upcoming") == "true"
    
    try:
        result = await client.get_hunts(
            page=page,
            per_page=per_page,
            active=active,
            previous=previous,
            upcoming=upcoming
        )
    except Exception as e:
        logger.error("Request failed in hunts: %s", str(e))
        return error_response("Internal Server Error", status=500)
    
    if result.get("error"):
        return error_response(
            result.get("message", "Failed to fetch hunts"),
            status=result.get("status", 500)
        )
    
    data = result.get("data", {})
    
    # Handle paginated response
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
    
    return json_response({
        "success": True,
        "data": data
    })

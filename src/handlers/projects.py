"""
Projects handler for the BLT API.
"""

import logging
from typing import Any, Dict
from utils import json_response, error_response, paginated_response, parse_pagination_params
from client import create_client


logger = logging.getLogger(__name__)

async def handle_projects(
    request: Any,
    env: Any,
    path_params: Dict[str, str],
    query_params: Dict[str, str],
    path: str
) -> Any:
    """
    Handle project-related requests.
    
    Endpoints:
        GET /projects - List projects with pagination
        GET /projects/{id} - Get a specific project
        GET /projects/{id}/contributors - Get project contributors
    """
    try:
        client = create_client(env)
    except Exception as e:
        logger.error("Failed to initialize client in projects: %s", str(e))
        return error_response("Service Unavailable", status=503)

    # Get specific project
    if "id" in path_params:
        project_id = path_params["id"]
        
        # Validate ID is numeric
        if not project_id.isdigit():
            return error_response("Invalid project ID", status=400)
        
        # Check if requesting contributors for project
        if path.endswith("/contributors"):
            try:
                result = await client.get_project(int(project_id))
            except Exception as e:
                logger.error("Request failed in projects: %s", str(e))
                return error_response("Internal Server Error", status=500)
            
            if result.get("error"):
                return error_response(
                    result.get("message", "Project not found"),
                    status=result.get("status", 404)
                )
            
            project_data = result.get("data", {})
            contributors = project_data.get("contributors", [])
            
            return json_response({
                "success": True,
                "project_id": int(project_id),
                "data": contributors,
                "count": len(contributors)
            })
        
        # Get project details
        try:
            result = await client.get_project(int(project_id))
        except Exception as e:
            logger.error("Request failed in projects: %s", str(e))
            return error_response("Internal Server Error", status=500)
        
        if result.get("error"):
            return error_response(
                result.get("message", "Project not found"),
                status=result.get("status", 404)
            )
        
        return json_response({
            "success": True,
            "data": result.get("data")
        })
    
    # List projects with pagination
    page, per_page = parse_pagination_params(query_params)
    search = query_params.get("search", query_params.get("q"))
    
    try:
        result = await client.get_projects(page=page, per_page=per_page, search=search)
    except Exception as e:
        logger.error("Request failed in projects: %s", str(e))
        return error_response("Internal Server Error", status=500)
    
    if result.get("error"):
        return error_response(
            result.get("message", "Failed to fetch projects"),
            status=result.get("status", 500)
        )
    
    data = result.get("data", {})
    
    # Handle the project list response format
    if isinstance(data, dict) and "projects" in data:
        return json_response({
            "success": True,
            "data": data.get("projects", []),
            "count": data.get("count", len(data.get("projects", [])))
        })
    
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

"""
Domains handler for the BLT API.
"""

import logging
from typing import Any, Dict
from utils import error_response, parse_pagination_params, convert_d1_results, json_response
from libs.db import get_db_safe
from models import Domain


async def handle_domains(
    request: Any,
    env: Any,
    path_params: Dict[str, str],
    query_params: Dict[str, str],
    path: str
) -> Any:
    """
    Handle all domain-related API requests using D1 database.

    This handler manages domain data stored in Cloudflare D1 (SQLite),
    providing listing, detail views, and tag associations.

    Endpoints:
        GET /domains - List all domains with pagination (ordered by creation date)
        GET /domains/{id} - Get detailed information for a specific domain
        GET /domains/{id}/tags - Get all tags associated with a domain (paginated)

    Query parameters for listing:
        - page: Page number for pagination (default: 1)
        - per_page: Items per page (default: 20, max: 100)

    Returns:
        JSON response with domain data and pagination metadata,
        or error response (400 for invalid ID, 404 for not found, 500 for DB errors)
    """
    logger = logging.getLogger(__name__)
    try:
        db = await get_db_safe(env)
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        return error_response("Database connection error", status=503)

    # Get specific domain
    if "id" in path_params:
        domain_id = path_params["id"]

        # Validate ID is numeric
        if not domain_id.isdigit():
            return error_response("Invalid domain ID", status=400)

        # GET /domains/{id}/tags
        if path.endswith("/tags"):
            try:
                page, per_page = parse_pagination_params(query_params)

                # GET total count first
                count_result = await db.prepare('''
                    SELECT COUNT(*) as total
                    FROM tags t
                    INNER JOIN domain_tags dt ON t.id = dt.tag_id
                    WHERE dt.domain_id = ?
                ''').bind(int(domain_id)).first()

                total = count_result.to_py().get('total', 0) if hasattr(count_result, 'to_py') else count_result.get('total', 0) if count_result else 0

                # JOIN query – kept as raw parameterized SQL because the ORM
                # does not yet support cross-table JOINs.
                result = await db.prepare('''
                    SELECT t.id, t.name, t.created
                    FROM tags t
                    INNER JOIN domain_tags dt ON t.id = dt.tag_id
                    WHERE dt.domain_id = ?
                    ORDER BY t.name
                    LIMIT ? OFFSET ?
                ''').bind(int(domain_id), per_page, (page - 1) * per_page).all()

                data = convert_d1_results(
                    result.results if hasattr(result, 'results') else []
                )

                return json_response({
                    "success": True,
                    "domain_id": int(domain_id),
                    "data": data,
                    "pagination": {
                        "page": page,
                        "per_page": per_page,
                        "count": len(data),
                        "total": total,
                        "total_pages": max(1, (total + per_page - 1) // per_page)
                    }
                })
            except Exception as e:
                logger.error(f"Error fetching domain tags: {str(e)}")
                return error_response("Failed to fetch domain tags", status=500)

        # GET /domains/{id}
        try:
            domain = await Domain.objects(db).get(id=int(domain_id))
            if not domain:
                return error_response("Domain not found", status=404)

            return json_response({"success": True, "data": domain})
        except Exception as e:
            logger.error(f"Error fetching domain: {str(e)}")
            return error_response("Failed to fetch domain", status=500)

    # GET /domains  –  list with pagination
    try:
        page, per_page = parse_pagination_params(query_params)

        total = await Domain.objects(db).count()
        data = (
            await Domain.objects(db)
            .order_by("-created")
            .paginate(page, per_page)
            .all()
        )

        return json_response({
            "success": True,
            "data": data,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "count": len(data),
                "total": total,
                "total_pages": max(1, (total + per_page - 1) // per_page)
            }
        })
    except Exception as e:
        logger.error(f"Error fetching domains: {str(e)}")
        return error_response("Failed to fetch domains", status=500)

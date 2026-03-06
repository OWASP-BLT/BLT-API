"""
Stats handler for the BLT API.
"""

import logging
from typing import Any, Dict
from utils import json_response, error_response
from libs.db import get_db_safe


async def handle_stats(
    request: Any,
    env: Any,
    path_params: Dict[str, str],
    query_params: Dict[str, str],
    path: str
) -> Any:
    """
    Handle statistics-related requests.

    Endpoints:
        GET /stats - Get overall platform statistics
    """
    logger = logging.getLogger(__name__)

    try:
        db = await get_db_safe(env)
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        return error_response(f"Database connection error: {str(e)}", status=500)

    try:
        bugs_result = await db.prepare(
            """
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(CASE WHEN status = 'open' THEN 1 ELSE 0 END), 0) AS open,
                COALESCE(SUM(CASE WHEN status = 'closed' THEN 1 ELSE 0 END), 0) AS closed
            FROM bugs
            """
        ).first()
        bugs_row = bugs_result.to_py() if hasattr(bugs_result, "to_py") else dict(bugs_result)
        bugs_count = bugs_row.get("total", 0)
        open_bugs_count = bugs_row.get("open", 0)
        closed_bugs_count = bugs_row.get("closed", 0)

        users_result = await db.prepare('SELECT COUNT(*) as count FROM users WHERE is_active = 1').first()
        users_count = (users_result.to_py() if hasattr(users_result, 'to_py') else dict(users_result)).get('count', 0)

        domains_result = await db.prepare('SELECT COUNT(*) as count FROM domains WHERE is_active = 1').first()
        domains_count = (domains_result.to_py() if hasattr(domains_result, 'to_py') else dict(domains_result)).get('count', 0)

        return json_response({
            "success": True,
            "data": {
                "bugs": bugs_count,
                "bug_breakdown": {
                    "open": open_bugs_count,
                    "closed": closed_bugs_count,
                },
                "users": users_count,
                "domains": domains_count,
            },
            "description": {
                "bugs": "Total number of bugs reported",
                "bug_breakdown": "Bug report counts by status",
                "users": "Total number of active registered users",
                "domains": "Total number of active tracked domains",
            }
        })
    except Exception as e:
        logger.error(f"Error fetching stats: {str(e)}")
        return error_response(f"Error fetching stats: {str(e)}", status=500)
    
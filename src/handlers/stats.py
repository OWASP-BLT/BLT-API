"""
Stats handler for the BLT API.
"""

import logging
from typing import Any, Dict
from utils import json_response, error_response, convert_single_d1_result
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
        bugs_result = await db.prepare('SELECT COUNT(*) as count FROM bugs').first()
        bugs_count = (await convert_single_d1_result(bugs_result)).get('count', 0)

        open_bugs_result = await db.prepare("SELECT COUNT(*) as count FROM bugs WHERE status = 'open'").first()
        open_bugs_count = (open_bugs_result.to_py() if hasattr(open_bugs_result, 'to_py') else dict(open_bugs_result)).get('count', 0)

        closed_bugs_result = await db.prepare("SELECT COUNT(*) as count FROM bugs WHERE status = 'closed'").first()
        closed_bugs_count = (closed_bugs_result.to_py() if hasattr(closed_bugs_result, 'to_py') else dict(closed_bugs_result)).get('count', 0)

        users_result = await db.prepare('SELECT COUNT(*) as count FROM users WHERE is_active = 1').first()
        users_count = (await convert_single_d1_result(users_result)).get('count', 0)

        domains_result = await db.prepare('SELECT COUNT(*) as count FROM domains WHERE is_active = 1').first()
        domains_count = (await convert_single_d1_result(domains_result)).get('count', 0)

        return json_response({
            "success": True,
            "data": {
                "bugs": {
                    "total": bugs_count,
                    "open": open_bugs_count,
                    "closed": closed_bugs_count,
                },
                "users": users_count,
                "domains": domains_count,
            },
            "description": {
                "bugs": "Bug report counts by status",
                "users": "Total number of active registered users",
                "domains": "Total number of active tracked domains",
            }
        })
    except Exception as e:
        logger.error(f"Error fetching stats: {str(e)}")
        return error_response(f"Error fetching stats: {str(e)}", status=500)
    

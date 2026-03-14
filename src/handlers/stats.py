"""
Stats handler for the BLT API.
"""
import logging
from typing import Any, Dict
from utils import json_response, error_response
from libs.db import get_db_safe
from models import Bug, User, Domain


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
    except Exception:
        logger.exception("Database connection error")
        return error_response("Database connection error", status=500)

    try:
        total_bugs = await Bug.objects(db).count()
        open_bugs = await Bug.objects(db).filter(status='open').count()
        closed_bugs = await Bug.objects(db).filter(status='closed').count()
        other_bugs = total_bugs - open_bugs - closed_bugs
        users_count = await User.objects(db).filter(is_active=1).count()
        active_users_count = users_count
        domains_count = await Domain.objects(db).filter(is_active=1).count()
        active_domains_count = domains_count

        return json_response({
            "success": True,
            "data": {
                "bugs": total_bugs,
                "bugs_breakdown": {
                    "total": total_bugs,
                    "open": open_bugs,
                    "closed": closed_bugs,
                    "other": other_bugs,
                },
                "users": users_count,
                "active_users": active_users_count,
                "domains": domains_count,
                "active_domains": active_domains_count,
            },
            "description": {
                "bugs": "Total number of bugs reported",
                "bugs_breakdown": "Bug counts by status (total, open, closed, other)",
                "users": "Total number of active registered users",
                "active_users": "Total number of active registered users",
                "domains": "Total number of active tracked domains",
                "active_domains": "Total number of active tracked domains",
            }
        })
    except Exception:
        logger.exception("Error fetching stats")
        return error_response("Internal server error", status=500)

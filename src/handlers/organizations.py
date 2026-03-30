"""
Organizations handler for the BLT API.
"""

from typing import Any, Dict
from utils import error_response, paginated_response, parse_pagination_params
from workers import Response
from libs.db import get_db_safe
from models import Organization, Domain, Bug, User, Tag, OrganizationManager, OrganizationTag, OrganizationIntegration

ALLOWED_ORG_TYPES = {"company", "nonprofit", "education"}


async def _get_organization_stats(db, org_id_int: int) -> dict:
    """Shared stats aggregation used by /stats endpoint and include=stats."""
    domain_count = await Domain.objects(db)\
        .filter(organization=org_id_int).count()
    bug_count = await Bug.objects(db)\
        .join("domains", on="bugs.domain = domains.id", join_type="INNER")\
        .filter(**{"domains.organization": org_id_int}).count()
    verified_bug_count = await Bug.objects(db)\
        .join("domains", on="bugs.domain = domains.id", join_type="INNER")\
        .filter(**{"domains.organization": org_id_int, "bugs.verified": 1}).count()
    manager_count = await OrganizationManager.objects(db)\
        .filter(organization_id=org_id_int).count()
    return {
        "domain_count": domain_count,
        "bug_count": bug_count,
        "verified_bug_count": verified_bug_count,
        "manager_count": manager_count,
    }


async def handle_organizations(
    request: Any,
    env: Any,
    path_params: Dict[str, str],
    query_params: Dict[str, str],
    path: str
) -> Any:
    """
    Handle organization-related requests.

    Endpoints:
        GET /organizations - List organizations with pagination and search
        GET /organizations/{id} - Get a specific organization with details
        GET /organizations/{id}/domains - Get organization domains
        GET /organizations/{id}/bugs - Get bugs from organization domains
        GET /organizations/{id}/managers - Get organization managers
        GET /organizations/{id}/tags - Get organization tags
        GET /organizations/{id}/integrations - Get organization integrations
        GET /organizations/{id}/stats - Get organization statistics
    """
    try:
        db = await get_db_safe(env)
    except Exception as e:
        print(f"Database connection error: {type(e).__name__}")
        return error_response("Service unavailable", status=503)

    # Get specific organization
    if "id" in path_params:
        org_id = path_params["id"]

        # Validate ID is numeric
        if not org_id.isdigit():
            return error_response("Invalid organization ID", status=400)

        org_id_int = int(org_id)

        # Verify org exists before dispatching to sub-resource routes
        try:
            org_exists = await Organization.objects(db).filter(id=org_id_int).count()
        except Exception as e:
            print(f"Error checking org existence: {type(e).__name__}")
            return error_response("Failed to verify organization", status=500)
        if not org_exists:
            return error_response("Organization not found", status=404)

        # GET /organizations/{id}/domains
        if path.endswith("/domains"):
            try:
                page, per_page = parse_pagination_params(query_params)
                domains = await Domain.objects(db)\
                    .filter(organization=org_id_int)\
                    .order_by('-created')\
                    .paginate(page, per_page)\
                    .values('id', 'name', 'url', 'logo', 'clicks', 'email',
                            'twitter', 'facebook', 'github', 'created', 'is_active')\
                    .all()
                total = await Domain.objects(db).filter(organization=org_id_int).count()
                return paginated_response(domains, page=page, per_page=per_page, total=total)
            except Exception as e:
                print(f"Error failed to fetch domains: {type(e).__name__}")
                return error_response("Failed to fetch domains. Please try again later.", status=500)

        # GET /organizations/{id}/bugs
        if path.endswith("/bugs"):
            try:
                page, per_page = parse_pagination_params(query_params)
                bugs = await Bug.objects(db)\
                    .join("domains", on="bugs.domain = domains.id", join_type="INNER")\
                    .filter(**{"domains.organization": org_id_int})\
                    .order_by('-bugs.created')\
                    .paginate(page, per_page)\
                    .values('bugs.id', 'bugs.url', 'bugs.description', 'bugs.verified',
                            'bugs.score', 'bugs.status', 'bugs.created',
                            'bugs.domain', 'domains.name AS domain_name')\
                    .all()
                total = await Bug.objects(db)\
                    .join("domains", on="bugs.domain = domains.id", join_type="INNER")\
                    .filter(**{"domains.organization": org_id_int})\
                    .count()
                return paginated_response(bugs, page=page, per_page=per_page, total=total)
            except Exception as e:
                print(f"Error failed to fetch bugs: {type(e).__name__}")
                return error_response("Failed to fetch bugs. Please try again later.", status=500)

        # GET /organizations/{id}/managers
        if path.endswith("/managers"):
            try:
                page, per_page = parse_pagination_params(query_params)
                total = await OrganizationManager.objects(db)\
                    .join("users", on="organization_managers.user_id = users.id", join_type="INNER")\
                    .filter(**{"organization_managers.organization_id": org_id_int}).count()
                managers = await OrganizationManager.objects(db)\
                    .join("users", on="organization_managers.user_id = users.id", join_type="INNER")\
                    .filter(**{"organization_managers.organization_id": org_id_int})\
                    .order_by('-organization_managers.created')\
                    .paginate(page, per_page)\
                    .values('users.id', 'users.username',
                            'users.user_avatar', 'users.total_score',
                            'organization_managers.created AS joined_as_manager')\
                    .all()
                return Response.json({
                    "success": True,
                    "data": managers,
                    "pagination": {
                        "page": page,
                        "per_page": per_page,
                        "total": total,
                    }
                })
            except Exception as e:
                print(f"Error fetching managers: {type(e).__name__}")
                return error_response("Failed to fetch managers. Please try again later.", status=500)

        # GET /organizations/{id}/tags
        if path.endswith("/tags"):
            try:
                tags = await OrganizationTag.objects(db)\
                    .join("tags", on="organization_tags.tag_id = tags.id", join_type="INNER")\
                    .filter(**{"organization_tags.organization_id": org_id_int})\
                    .order_by('tags.name')\
                    .values('tags.id', 'tags.name', 'organization_tags.created')\
                    .all()
                return Response.json({
                    "success": True,
                    "data": tags,
                    "count": len(tags)
                })
            except Exception as e:
                print(f"Error failed to fetch tags: {type(e).__name__}")
                return error_response("Failed to fetch tags. Please try again later.", status=500)

        # GET /organizations/{id}/integrations
        if path.endswith("/integrations"):
            try:
                integrations = await OrganizationIntegration.objects(db)\
                    .filter(organization_id=org_id_int)\
                    .order_by('integration_type')\
                    .values('id', 'integration_type', 'integration_name',
                            'is_active', 'created', 'modified')\
                    .all()
                return Response.json({
                    "success": True,
                    "data": integrations,
                    "count": len(integrations)
                })
            except Exception as e:
                print(f"Error failed to fetch integrations: {type(e).__name__}")
                return error_response("Failed to fetch integrations. Please try again later.", status=500)

        # GET /organizations/{id}/stats
        if path.endswith("/stats"):
            try:
                stats = await _get_organization_stats(db, org_id_int)
                return Response.json({"success": True, "data": stats})
            except Exception as e:
                print(f"Error failed to fetch stats: {type(e).__name__}")
                return error_response("Failed to fetch stats. Please try again later.", status=500)

        # GET /organizations/{id} — organization details
        try:
            org = await Organization.objects(db)\
                .join("users", on="organization.admin = users.id", join_type="LEFT")\
                .filter(**{"organization.id": org_id_int})\
                .values('organization.id', 'organization.name', 'organization.slug',
                        'organization.description', 'organization.logo', 'organization.url',
                        'organization.type', 'organization.is_active', 'organization.team_points',
                        'organization.created', 'organization.tagline',
                        'users.username')\
                .first()

            if not org:
                return error_response("Organization not found", status=404)

            # Optionally include related data
            include_related = [i.strip().lower() for i in query_params.get("include", "").split(",")]

            if "managers" in include_related:
                org["managers"] = await OrganizationManager.objects(db)\
                    .join("users", on="organization_managers.user_id = users.id", join_type="INNER")\
                    .filter(**{"organization_managers.organization_id": org_id_int})\
                    .values('users.id', 'users.username', 'users.user_avatar')\
                    .all()

            if "tags" in include_related:
                org["tags"] = await OrganizationTag.objects(db)\
                    .join("tags", on="organization_tags.tag_id = tags.id", join_type="INNER")\
                    .filter(**{"organization_tags.organization_id": org_id_int})\
                    .values('tags.id', 'tags.name')\
                    .all()

            if "stats" in include_related:
                org["stats"] = await _get_organization_stats(db, org_id_int)

            return Response.json({"success": True, "data": org})
        except Exception as e:
            print(f"Error failed to fetch organization: {type(e).__name__}")
            return error_response("Failed to fetch organization. Please try again later.", status=500)

    # GET /organizations — list with pagination and search
    try:
        page, per_page = parse_pagination_params(query_params)
        search = query_params.get("search", query_params.get("q", "")).strip()
        org_type = query_params.get("type", "").strip()
        is_active = query_params.get("is_active", "").strip()

        qs = Organization.objects(db)\
            .join("users", on="organization.admin = users.id", join_type="LEFT")\
            .values('organization.id', 'organization.name', 'organization.slug',
                    'organization.description', 'organization.logo', 'organization.url',
                    'organization.type', 'organization.is_active', 'organization.team_points',
                    'organization.created', 'organization.tagline',
                    'users.username')\
            .order_by('-organization.created')

        # Build shared filter kwargs for both list and count queries
        filter_kwargs = {}
        if org_type:
            if org_type in ALLOWED_ORG_TYPES:
                filter_kwargs["type"] = org_type
            else:
                return error_response(
                    f"Invalid value for type: {org_type!r}. Use one of: {', '.join(sorted(ALLOWED_ORG_TYPES))}.",
                    status=400
                )
        if is_active:
            if is_active.lower() in ["true", "1", "yes"]:
                filter_kwargs["is_active"] = 1
            elif is_active.lower() in ["false", "0", "no"]:
                filter_kwargs["is_active"] = 0
            else:
                return error_response(
                    f"Invalid value for is_active: {is_active!r}. Use true/false.",
                    status=400
                )

        if search:
            qs = qs.filter_or(**{
                "organization.name__icontains": search,
                "organization.slug__icontains": search,
                "organization.description__icontains": search,
            })
        if filter_kwargs:
            qs = qs.filter(**{f"organization.{k}": v for k, v in filter_kwargs.items()})

        organizations = await qs.paginate(page, per_page).all()

        # Count query uses same filters without JOIN for consistency
        count_qs = Organization.objects(db)
        if search:
            count_qs = count_qs.filter_or(
                name__icontains=search,
                slug__icontains=search,
                description__icontains=search,
            )
        if filter_kwargs:
            count_qs = count_qs.filter(**filter_kwargs)
        total = await count_qs.count()

        return paginated_response(organizations, page=page, per_page=per_page, total=total)
    except Exception as e:
        print(f"Error failed to fetch organizations: {type(e).__name__}")
        return error_response("Failed to fetch organizations. Please try again later.", status=500)

"""
Organizations handler for the BLT API.
"""

from typing import Any, Dict
from utils import error_response, paginated_response, parse_pagination_params
from workers import Response
from libs.db import get_db_safe
from models import Organization, Domain, Bug, User, Tag, OrganizationManager, OrganizationTag, OrganizationIntegration


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
        return error_response(str(e), status=503)

    # Get specific organization
    if "id" in path_params:
        org_id = path_params["id"]

        # Validate ID is numeric
        if not org_id.isdigit():
            return error_response("Invalid organization ID", status=400)

        org_id_int = int(org_id)

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
                return error_response(f"Failed to fetch domains: {str(e)}", status=500)

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
                return error_response(f"Failed to fetch bugs: {str(e)}", status=500)

        # GET /organizations/{id}/managers
        if path.endswith("/managers"):
            try:
                managers = await OrganizationManager.objects(db)\
                    .join("users", on="organization_managers.user_id = users.id", join_type="INNER")\
                    .filter(**{"organization_managers.organization_id": org_id_int})\
                    .order_by('-organization_managers.created')\
                    .values('users.id', 'users.username', 'users.email',
                            'users.user_avatar', 'users.total_score',
                            'organization_managers.created AS joined_as_manager')\
                    .all()
                return Response.json({
                    "success": True,
                    "data": managers,
                    "count": len(managers)
                })
            except Exception as e:
                return error_response(f"Failed to fetch managers: {str(e)}", status=500)

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
                return error_response(f"Failed to fetch tags: {str(e)}", status=500)

        # GET /organizations/{id}/integrations
        if path.endswith("/integrations"):
            try:
                integrations = await OrganizationIntegration.objects(db)\
                    .filter(organization_id=org_id_int)\
                    .order_by('integration_type')\
                    .values('id', 'integration_type', 'integration_name',
                            'webhook_url', 'is_active', 'created', 'modified')\
                    .all()
                return Response.json({
                    "success": True,
                    "data": integrations,
                    "count": len(integrations)
                })
            except Exception as e:
                return error_response(f"Failed to fetch integrations: {str(e)}", status=500)

        # GET /organizations/{id}/stats
        if path.endswith("/stats"):
            try:
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
                return Response.json({
                    "success": True,
                    "data": {
                        "domain_count": domain_count,
                        "bug_count": bug_count,
                        "verified_bug_count": verified_bug_count,
                        "manager_count": manager_count
                    }
                })
            except Exception as e:
                return error_response(f"Failed to fetch stats: {str(e)}", status=500)

        # GET /organizations/{id} — organization details
        try:
            org = await Organization.objects(db)\
                .join("users", on="organization.admin = users.id", join_type="LEFT")\
                .filter(**{"organization.id": org_id_int})\
                .values('organization.id', 'organization.name', 'organization.slug',
                        'organization.description', 'organization.logo', 'organization.url',
                        'organization.type', 'organization.is_active', 'organization.team_points',
                        'organization.created', 'organization.tagline',
                        'users.username', 'users.email')\
                .first()

            if not org:
                return error_response("Organization not found", status=404)

            # Optionally include related data
            include_related = query_params.get("include", "").split(",")

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
                org["domain_count"] = await Domain.objects(db)\
                    .filter(organization=org_id_int).count()

            return Response.json({"success": True, "data": org})
        except Exception as e:
            return error_response(f"Failed to fetch organization: {str(e)}", status=500)

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
        if org_type and org_type in ["company", "nonprofit", "education"]:
            filter_kwargs["type"] = org_type
        if is_active:
            filter_kwargs["is_active"] = 1 if is_active.lower() in ["true", "1", "yes"] else 0

        if search:
            qs = qs.filter(**{"organization.name__icontains": search})
        if filter_kwargs:
            qs = qs.filter(**{f"organization.{k}": v for k, v in filter_kwargs.items()})

        organizations = await qs.paginate(page, per_page).all()

        # Count query uses same filters without JOIN for consistency
        count_qs = Organization.objects(db)
        if search:
            count_qs = count_qs.filter(name__icontains=search)
        if filter_kwargs:
            count_qs = count_qs.filter(**filter_kwargs)
        total = await count_qs.count()

        return paginated_response(organizations, page=page, per_page=per_page, total=total)
    except Exception as e:
        return error_response(f"Failed to fetch organizations: {str(e)}", status=500)

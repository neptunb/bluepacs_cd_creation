"""Auth-related API (Cloudflare Access identity for UI)."""

from __future__ import annotations

from sanic import Blueprint, json as json_response

from services.cloudflare_identity import identity_from_request

auth_bp = Blueprint("auth")


@auth_bp.route("/identity", methods=["GET"])
async def get_identity(request):
    """Identity for header tagline (Cloudflare Access headers / JWT claims)."""
    data = identity_from_request(request)
    return json_response(data)

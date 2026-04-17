"""Derive display name from Cloudflare Access headers / JWT (Ultramar-style)."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any, Optional

from sanic import Request

logger = logging.getLogger(__name__)


def _jwt_payload_unverified(token: str) -> Optional[dict[str, Any]]:
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        payload_b64 = parts[1]
        pad = "=" * ((4 - len(payload_b64) % 4) % 4)
        raw = base64.urlsafe_b64decode(payload_b64 + pad)
        return json.loads(raw.decode("utf-8"))
    except Exception:
        logger.debug("Could not parse Cf-Access-Jwt-Assertion payload", exc_info=True)
        return None


def _header(request: Request, *candidates: str) -> Optional[str]:
    for name in candidates:
        v = request.headers.get(name)
        if v and str(v).strip():
            return str(v).strip()
    return None


def _email_from_payload(payload: dict[str, Any]) -> Optional[str]:
    for key in ("email", "preferred_username"):
        v = payload.get(key)
        if isinstance(v, str) and "@" in v:
            return v.strip()
    return None


def _name_from_payload(payload: dict[str, Any]) -> Optional[str]:
    name = payload.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    gn = payload.get("given_name")
    fn = payload.get("family_name")
    if not gn and not fn:
        return None
    parts = [str(gn).strip() if gn else "", str(fn).strip() if fn else ""]
    combined = " ".join(p for p in parts if p).strip()
    return combined or None


def identity_from_request(request: Request) -> dict[str, Optional[str]]:
    """
    Reads Cloudflare Access identity from the incoming request (same headers as
    Ultramar phpapi/.../cloudflare-headers.php).
    """
    email = _header(
        request,
        "Cf-Access-Authenticated-User-Email",
        "cf-access-authenticated-user-email",
    )
    user_name = _header(request, "Cf-Access-User-Name", "cf-access-user-name")
    if user_name:
        return {"display_name": user_name, "email": email}

    jwt_token = _header(request, "Cf-Access-Jwt-Assertion", "cf-access-jwt-assertion")
    if not jwt_token:
        return {"display_name": None, "email": email}

    payload = _jwt_payload_unverified(jwt_token) or {}
    resolved = email or _email_from_payload(payload)
    display = _name_from_payload(payload)
    if display:
        return {"display_name": display, "email": resolved}
    return {"display_name": None, "email": resolved}

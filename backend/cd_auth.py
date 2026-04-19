"""Ultramar PHP session + P_CAN_USE_CD_CREATION validation for CD API."""

from __future__ import annotations

import logging
import os
from typing import Optional

import aiohttp
from sanic import Request
from sanic.response import json as json_response

from config import config

logger = logging.getLogger(__name__)


def _internal_token() -> str:
    """Shared secret for server-to-server calls from the Ultramar phpapi
    container. Bypasses the cookie check because those callers cannot forward
    a browser session cookie. Only effective when the env var is non-empty."""
    return (os.getenv("CD_INTERNAL_TOKEN") or "").strip()


def _forwarded_host(request: Request) -> str:
    h = request.headers.get("x-forwarded-host") or request.headers.get("X-Forwarded-Host")
    h = h or request.headers.get("host") or request.headers.get("Host")
    return (h or "localhost").split(":")[0]


async def validate_ultramar_cd_access(request: Request) -> tuple[bool, Optional[str]]:
    """
    Returns (allowed, error_code).
    Forwards Cookie and Host headers to PHP cd_access_check.php.
    """
    url = (config.CD_AUTH_VALIDATE_URL or "").strip()
    if not url:
        logger.warning("CD_AUTH_VALIDATE_URL not set; allowing request (dev mode)")
        return True, None

    cookie = request.headers.get("cookie") or request.headers.get("Cookie")
    if not cookie:
        return False, "no_cookie"

    headers = {
        "Cookie": cookie,
        "X-Forwarded-Host": _forwarded_host(request),
        "Accept": "application/json",
    }

    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    return False, f"php_status_{resp.status}"
                try:
                    data = await resp.json()
                except Exception:
                    return False, "invalid_php_json"
                if isinstance(data, dict) and data.get("allowed") is True:
                    return True, None
                err = data.get("error") if isinstance(data, dict) else None
                return False, str(err or "not_allowed")
    except aiohttp.ClientError as e:
        logger.exception("CD auth request failed: %s", e)
        return False, "auth_service_unreachable"


async def cd_auth_middleware(request: Request):
    if request.method == "OPTIONS":
        return
    path = request.path
    if path == "/api/health" or path.startswith("/api/health"):
        return

    expected = _internal_token()
    if expected:
        supplied = (
            request.headers.get("x-internal-auth")
            or request.headers.get("X-Internal-Auth")
            or ""
        ).strip()
        if supplied and supplied == expected:
            return  # trusted server-to-server caller (same Docker network)

    allowed, err = await validate_ultramar_cd_access(request)
    if not allowed:
        return json_response(
            {"error": err or "forbidden", "detail": "CD access denied by Ultramar"},
            status=403,
        )

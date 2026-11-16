"""Fire-and-forget note to logd. A failure here never affects the caller."""

from __future__ import annotations

import json
import os
import threading
import urllib.request


def bp_log(event: str, detail: str, user: str = "-") -> None:
    url = (os.getenv("LOGD_URL") or "http://logd:8090/log").strip()
    body = json.dumps(
        {
            "service": "cd-backend",
            "user": user or "-",
            "event": " ".join(str(event).split()),
            "detail": " ".join(str(detail).split()),
        }
    ).encode("utf-8")

    def send() -> None:
        try:
            req = urllib.request.Request(
                url,
                data=body,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=0.4) as resp:
                resp.read()
        except Exception:
            return

    threading.Thread(target=send, daemon=True).start()


def request_log_user(request, fallback: str = "-") -> str:
    """Name and userid captured when Ultramar accepted this request."""
    ctx = getattr(request, "ctx", None)
    user = getattr(ctx, "log_user", None) if ctx is not None else None
    if isinstance(user, str):
        user = " ".join(user.split())
        if user and user != "-":
            return user
    if isinstance(fallback, str):
        fallback = " ".join(fallback.split())
        if fallback:
            return fallback
    return "-"


def client_ip(request) -> str:
    raw = (
        request.headers.get("cf-connecting-ip")
        or request.headers.get("x-forwarded-for")
        or ""
    )
    ip = raw.split(",")[0].strip()
    if ip:
        return ip
    remote = getattr(request, "ip", None) or "-"
    return str(remote)

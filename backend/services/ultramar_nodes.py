"""
Fetches the list of DICOM nodes from Ultramar (phpapi) for the CD Creator UI.

The actual CRUD for nodes lives in the Ultramar uploader's
"User Menu -> Settings -> DICOM Modalities (Pacs Yerleri)" section and is
backed by the `dicom_modalities` MySQL table. Ultramar exposes the list via
`phpapi/.../user_public/assets/cd/cd_nodes_list.php`, which validates the
user's session cookie + `P_CAN_USE_CD_CREATION` privilege (same guard as
`cd_access_check.php`).

In local development (ULTRAMAR_NODES_URL empty) a JSON sample file is used as
a fallback so the CD Creator can still boot without the PHP backend.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

import aiohttp
from sanic import Request

from config import config

logger = logging.getLogger(__name__)


def _forwarded_host(request: Request) -> str:
    h = request.headers.get("x-forwarded-host") or request.headers.get("X-Forwarded-Host")
    h = h or request.headers.get("host") or request.headers.get("Host")
    return (h or "localhost").split(":")[0]


def _normalize_node(raw: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Convert the Ultramar modality shape into the CD Creator node shape.

    Ultramar DB columns (dicom_modalities):
        NAME, AET, IP_4, PORT,
        REMOTE_DICOM_AE, ORTHANC_URL, ORTHANC_USER, ORTHANC_PASSWORD

    We also accept an already-normalized shape (lowercase keys) so the sample
    JSON fallback works without transformation.
    """
    if not isinstance(raw, dict):
        return None

    ae_title = (
        raw.get("ae_title")
        or raw.get("AET")
        or raw.get("AE_TITLE")
        or ""
    )
    host = raw.get("host") or raw.get("IP_4") or raw.get("IP") or ""
    port = raw.get("port") or raw.get("PORT")
    name = raw.get("name") or raw.get("NAME") or ae_title

    ae_title = str(ae_title).strip()
    host = str(host).strip()
    if not ae_title or not host or port in (None, ""):
        return None
    try:
        port_int = int(port)
    except (TypeError, ValueError):
        return None

    def _opt(*keys: str) -> Optional[str]:
        for k in keys:
            v = raw.get(k)
            if v is None:
                continue
            text = str(v).strip()
            if text:
                return text
        return None

    node: dict[str, Any] = {
        "ae_title": ae_title,
        "host": host,
        "port": port_int,
        "name": str(name).strip() or ae_title,
    }
    remote_dicom_ae = _opt("remote_dicom_ae", "REMOTE_DICOM_AE")
    orthanc_url = _opt("orthanc_url", "ORTHANC_URL")
    orthanc_user = _opt("orthanc_user", "ORTHANC_USER")
    orthanc_password = _opt("orthanc_password", "ORTHANC_PASSWORD")
    if remote_dicom_ae:
        node["remote_dicom_ae"] = remote_dicom_ae
    if orthanc_url:
        node["orthanc_url"] = orthanc_url
    if orthanc_user:
        node["orthanc_user"] = orthanc_user
    if orthanc_password:
        node["orthanc_password"] = orthanc_password
    return node


def _load_sample_nodes() -> list[dict[str, Any]]:
    path = Path(config.ULTRAMAR_NODES_SAMPLE)
    if not path.exists():
        return []
    try:
        with open(path, "r") as f:
            data = json.load(f)
        if isinstance(data, dict):
            data = data.get("nodes") or []
        if not isinstance(data, list):
            return []
        nodes = []
        for entry in data:
            normalized = _normalize_node(entry)
            if normalized:
                nodes.append(normalized)
        return nodes
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to read sample nodes file %s: %s", path, exc)
        return []


async def _fetch_from_ultramar(request: Request) -> list[dict[str, Any]]:
    url = config.ULTRAMAR_NODES_URL
    if not url:
        return _load_sample_nodes()

    cookie = request.headers.get("cookie") or request.headers.get("Cookie") or ""
    headers = {
        "Accept": "application/json",
        "X-Forwarded-Host": _forwarded_host(request),
    }
    if cookie:
        headers["Cookie"] = cookie

    timeout = aiohttp.ClientTimeout(total=10)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as resp:
                if resp.status != 200:
                    logger.warning(
                        "Ultramar nodes endpoint returned HTTP %s for %s",
                        resp.status,
                        url,
                    )
                    return []
                payload = await resp.json(content_type=None)
    except (aiohttp.ClientError, json.JSONDecodeError) as exc:
        logger.exception("Failed to fetch DICOM nodes from Ultramar: %s", exc)
        return []

    # PHP endpoint returns { "nodes": [...] } (preferred) or a bare list.
    if isinstance(payload, dict):
        raw_list = payload.get("nodes") or payload.get("veri") or []
    elif isinstance(payload, list):
        raw_list = payload
    else:
        raw_list = []

    nodes: list[dict[str, Any]] = []
    for entry in raw_list:
        normalized = _normalize_node(entry)
        if normalized:
            nodes.append(normalized)
    return nodes


async def fetch_nodes(request: Request) -> list[dict[str, Any]]:
    """Return the latest DICOM node list (empty list on failure)."""
    return await _fetch_from_ultramar(request)


async def fetch_node(
    request: Request, ae_title: str
) -> Optional[dict[str, Any]]:
    """Return a single node by AE Title (case-sensitive), or None."""
    if not ae_title:
        return None
    nodes = await _fetch_from_ultramar(request)
    for node in nodes:
        if node["ae_title"] == ae_title:
            return node
    return None

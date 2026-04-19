"""
Read-only DICOM node API for the CD Creator UI.

Node CRUD lives in Ultramar (uploader -> User Menu -> Settings -> DICOM
Modalities / Pacs Yerleri). This blueprint only *reads* from Ultramar and
exposes a C-ECHO helper for the selected node.
"""

import logging

from sanic import Blueprint, json as json_response
from sanic.request import Request

from config import config
from services.dicom_query import DicomQueryService
from services.ultramar_nodes import fetch_node, fetch_nodes

logger = logging.getLogger(__name__)

nodes_bp = Blueprint("nodes")


@nodes_bp.route("/", methods=["GET"])
async def list_nodes(request: Request):
    nodes = await fetch_nodes(request)
    return json_response({"nodes": nodes})


@nodes_bp.route("/echo", methods=["POST"])
async def echo_node(request: Request):
    body = request.json or {}
    ae_title = body.get("ae_title")

    node = await fetch_node(request, ae_title)
    if not node:
        return json_response({"error": f"Unknown node: {ae_title}"}, status=404)

    service = DicomQueryService(
        local_ae=config.local_ae_title,
        remote_ae=config.dicom_remote_ae(node),
        remote_host=node["host"],
        remote_port=node["port"],
    )

    success = await service.verify()
    return json_response({"ae_title": ae_title, "reachable": success})


@nodes_bp.route("/echo-direct", methods=["POST"])
async def echo_node_direct(request: Request):
    """Run a raw C-ECHO against arbitrary host/port/AET without consulting the
    Ultramar node list. Used by Ultramar's 'Pacs Yerleri' Echo button so a row
    can be verified even before it is persisted or while it is being edited.

    Mirrors the logic of /echo exactly (same local_ae, same remote_ae
    resolution via config.dicom_remote_ae) but skips the fetch_node step.
    """
    body = request.json or {}
    ae_title = (body.get("ae_title") or "").strip()
    host = (body.get("host") or "").strip()
    port = body.get("port")
    remote_dicom_ae = (
        body.get("remote_dicom_ae") or body.get("remote_ae") or ""
    ).strip()

    try:
        port_int = int(port) if port not in (None, "") else 0
    except (TypeError, ValueError):
        port_int = 0

    if not ae_title or not host or port_int <= 0:
        return json_response(
            {
                "error": "Missing fields",
                "ae_title": ae_title,
                "host": host,
                "port": port_int,
                "reachable": False,
            },
            status=400,
        )

    node = {"ae_title": ae_title, "host": host, "port": port_int}
    if remote_dicom_ae:
        node["remote_dicom_ae"] = remote_dicom_ae

    local_ae = config.local_ae_title
    remote_ae = config.dicom_remote_ae(node)

    logger.info(
        "echo-direct: local_ae=%s remote_ae=%s host=%s port=%s",
        local_ae, remote_ae, host, port_int,
    )

    service = DicomQueryService(
        local_ae=local_ae,
        remote_ae=remote_ae,
        remote_host=host,
        remote_port=port_int,
    )

    try:
        detail = await service.verify_detailed()
        reachable = bool(detail.get("reachable"))
        error = None if reachable else (detail.get("reason") or "unreachable")
    except Exception as exc:
        logger.exception("echo-direct verify raised")
        reachable = False
        error = f"verify raised: {exc}"

    logger.info(
        "echo-direct result: reachable=%s error=%s (local_ae=%s remote_ae=%s host=%s port=%s)",
        reachable, error, local_ae, remote_ae, host, port_int,
    )

    return json_response({
        "ae_title": ae_title,
        "host": host,
        "port": port_int,
        "local_ae": local_ae,
        "remote_ae": remote_ae,
        "reachable": reachable,
        "error": error,
    })

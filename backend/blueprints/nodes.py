"""
Read-only DICOM node API for the CD Creator UI.

Node CRUD lives in Ultramar (uploader -> User Menu -> Settings -> DICOM
Modalities / Pacs Yerleri). This blueprint only *reads* from Ultramar and
exposes a C-ECHO helper for the selected node.
"""

from sanic import Blueprint, json as json_response
from sanic.request import Request

from config import config
from services.dicom_query import DicomQueryService
from services.ultramar_nodes import fetch_node, fetch_nodes

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

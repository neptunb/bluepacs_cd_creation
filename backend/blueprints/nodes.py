from sanic import Blueprint, json as json_response
from sanic.request import Request

from services.dicom_query import DicomQueryService
from config import config

nodes_bp = Blueprint("nodes")


@nodes_bp.route("/", methods=["GET"])
async def list_nodes(request: Request):
    return json_response({"nodes": config.get_nodes()})


@nodes_bp.route("/", methods=["POST"])
async def add_node(request: Request):
    body = request.json
    required = ["ae_title", "host", "port"]
    if not all(k in body for k in required):
        return json_response(
            {"error": f"Missing required fields: {required}"}, status=400
        )

    node = {
        "ae_title": body["ae_title"].strip().upper(),
        "host": body["host"].strip(),
        "port": int(body["port"]),
        "name": body.get("name", "").strip() or body["ae_title"],
    }

    try:
        config.add_node(node)
    except ValueError as e:
        return json_response({"error": str(e)}, status=409)

    return json_response({"node": node}, status=201)


@nodes_bp.route("/<ae_title:str>", methods=["PUT"])
async def update_node(request: Request, ae_title: str):
    body = request.json
    updates = {}
    if "host" in body:
        updates["host"] = body["host"].strip()
    if "port" in body:
        updates["port"] = int(body["port"])
    if "name" in body:
        updates["name"] = body["name"].strip()

    try:
        config.update_node(ae_title, updates)
    except ValueError as e:
        return json_response({"error": str(e)}, status=404)

    return json_response({"status": "updated"})


@nodes_bp.route("/<ae_title:str>", methods=["DELETE"])
async def delete_node(request: Request, ae_title: str):
    config.remove_node(ae_title)
    return json_response({"status": "deleted"})


@nodes_bp.route("/echo", methods=["POST"])
async def echo_node(request: Request):
    body = request.json
    ae_title = body.get("ae_title")

    node = config.get_node(ae_title)
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

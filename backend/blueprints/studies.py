import logging

from sanic import Blueprint, json as json_response
from sanic.request import Request

from services.dicom_query import DicomQueryService
from services.orthanc_api import OrthancApiService
from config import config

logger = logging.getLogger(__name__)

studies_bp = Blueprint("studies")


@studies_bp.route("/recent", methods=["POST"])
async def recent_studies(request: Request):
    body = request.json or {}
    ae_title = body.get("node_ae_title")
    if not ae_title:
        return json_response({"error": "node_ae_title is required"}, status=400)

    try:
        limit = int(body.get("limit", 10))
    except (TypeError, ValueError):
        limit = 10

    study_date_from = body.get("study_date_from")
    study_date_to = body.get("study_date_to")
    if study_date_from is not None:
        study_date_from = str(study_date_from).strip() or None
    if study_date_to is not None:
        study_date_to = str(study_date_to).strip() or None

    node = config.get_node(ae_title)
    if not node:
        return json_response({"error": f"Unknown node: {ae_title}"}, status=404)

    service = _get_service(node)

    try:
        studies = await service.find_recent_studies(
            limit=limit,
            study_date_from=study_date_from,
            study_date_to=study_date_to,
        )
    except Exception as e:
        logger.exception("Recent studies failed for node %s", node["ae_title"])
        return json_response(
            {"error": f"Recent studies failed: {e}", "studies": []}, status=500
        )

    return json_response({"studies": studies})


def _get_service(node: dict):
    orthanc_url = node.get("orthanc_url")
    if orthanc_url:
        ou, op = config.orthanc_http_credentials(node)
        return OrthancApiService(
            orthanc_url=orthanc_url,
            username=ou,
            password=op,
        )
    return DicomQueryService(
        local_ae=config.local_ae_title,
        remote_ae=node["ae_title"],
        remote_host=node["host"],
        remote_port=node["port"],
    )


@studies_bp.route("/<study_uid:str>/series", methods=["POST"])
async def get_series(request: Request, study_uid: str):
    body = request.json or {}
    ae_title = body.get("node_ae_title")
    if not ae_title:
        return json_response({"error": "node_ae_title is required"}, status=400)

    node = config.get_node(ae_title)
    if not node:
        return json_response({"error": f"Unknown node: {ae_title}"}, status=404)

    service = _get_service(node)

    try:
        series_list = await service.find_series(study_instance_uid=study_uid)
    except Exception as e:
        logger.exception("Series search failed for node %s", node["ae_title"])
        return json_response(
            {"error": f"Series search failed: {e}", "series": []}, status=500
        )

    return json_response({"series": series_list})

import logging

from sanic import Blueprint, json as json_response
from sanic.request import Request

from services.dicom_query import DicomQueryService
from services.orthanc_api import OrthancApiService
from models.schemas import PatientQuery
from config import config

logger = logging.getLogger(__name__)

patients_bp = Blueprint("patients")


def _get_service(node: dict):
    """Return OrthancApiService if orthanc_url is set, else DicomQueryService."""
    orthanc_url = node.get("orthanc_url")
    if orthanc_url:
        ou, op = config.orthanc_http_credentials(node)
        logger.info("Using Orthanc REST API at %s for %s", orthanc_url, node["ae_title"])
        return OrthancApiService(
            orthanc_url=orthanc_url,
            username=ou,
            password=op,
        )
    logger.info("Using DICOM C-FIND for %s", node["ae_title"])
    return DicomQueryService(
        local_ae=config.local_ae_title,
        remote_ae=config.dicom_remote_ae(node),
        remote_host=node["host"],
        remote_port=node["port"],
    )


@patients_bp.route("/search", methods=["POST"])
async def search_patients(request: Request):
    try:
        query = PatientQuery(**request.json)
    except Exception as e:
        return json_response({"error": str(e)}, status=400)

    node = config.get_node(query.node_ae_title)
    if not node:
        return json_response(
            {"error": f"Unknown node: {query.node_ae_title}"}, status=404
        )

    service = _get_service(node)

    try:
        patients = await service.find_patients(
            patient_name=query.patient_name or "",
            patient_id=query.patient_id or "",
            study_date_from=query.study_date_from,
            study_date_to=query.study_date_to,
        )
    except Exception as e:
        logger.exception("Patient search failed for node %s", node["ae_title"])
        return json_response(
            {"error": f"Search failed: {e}", "patients": []}, status=500
        )

    return json_response({"patients": patients})


@patients_bp.route("/<patient_id:str>/studies", methods=["POST"])
async def get_patient_studies(request: Request, patient_id: str):
    body = request.json or {}
    ae_title = body.get("node_ae_title")
    if not ae_title:
        return json_response({"error": "node_ae_title is required"}, status=400)

    node = config.get_node(ae_title)
    if not node:
        return json_response({"error": f"Unknown node: {ae_title}"}, status=404)

    service = _get_service(node)

    modality = body.get("modality")
    study_date_from = body.get("study_date_from")
    study_date_to = body.get("study_date_to")

    try:
        studies = await service.find_studies(
            patient_id=patient_id,
            modality=modality,
            study_date_from=study_date_from,
            study_date_to=study_date_to,
        )
    except Exception as e:
        logger.exception("Study search failed for node %s", node["ae_title"])
        return json_response(
            {"error": f"Study search failed: {e}", "studies": []}, status=500
        )

    return json_response({"studies": studies})


@patients_bp.route("/test-cfind", methods=["POST"])
async def test_cfind(request: Request):
    """Diagnostic endpoint — returns raw C-FIND debug info."""
    body = request.json or {}
    ae_title = body.get("node_ae_title")
    if not ae_title:
        return json_response({"error": "node_ae_title is required"}, status=400)

    node = config.get_node(ae_title)
    if not node:
        return json_response({"error": f"Unknown node: {ae_title}"}, status=404)

    service = DicomQueryService(
        local_ae=config.local_ae_title,
        remote_ae=config.dicom_remote_ae(node),
        remote_host=node["host"],
        remote_port=node["port"],
    )

    diag = await service.diagnostic_cfind(
        patient_name=body.get("patient_name", ""),
        patient_id=body.get("patient_id", ""),
    )

    return json_response(diag)

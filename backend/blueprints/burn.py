import os
import uuid
import logging
from threading import Lock

from sanic import Blueprint, json as json_response
from sanic.request import Request
from sanic.response import file_stream

from models.schemas import BurnRequest
from services.cd_builder import CdBuilderService
from config import config

logger = logging.getLogger(__name__)

burn_bp = Blueprint("burn")

active_jobs: dict[str, dict] = {}
job_locks: dict[str, Lock] = {}


@burn_bp.route("/create", methods=["POST"])
async def create_cd(request: Request):
    try:
        burn_req = BurnRequest(**request.json)
    except Exception as e:
        return json_response({"error": str(e)}, status=400)

    node = config.get_node(burn_req.node_ae_title)
    if not node:
        return json_response(
            {"error": f"Unknown node: {burn_req.node_ae_title}"}, status=404
        )

    job_id = str(uuid.uuid4())
    active_jobs[job_id] = {
        "status": "queued",
        "progress": 0.0,
        "message": "Job queued",
        "output_path": None,
        "filename": None,
        "retrieved_instances": 0,
        "expected_instances": burn_req.expected_instances,
    }
    job_locks[job_id] = Lock()

    app = request.app
    app.add_task(
        _run_build_job(job_id, burn_req, node),
        name=f"build_{job_id}",
    )

    return json_response({"job_id": job_id, "status": "queued"})


@burn_bp.route("/status/<job_id:str>", methods=["GET"])
async def get_status(request: Request, job_id: str):
    job = active_jobs.get(job_id)
    if not job:
        return json_response({"error": "Job not found"}, status=404)

    return json_response({
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "message": job["message"],
        "filename": job["filename"],
        "download_ready": job["status"] == "complete" and job["output_path"] is not None,
        "retrieved_instances": job.get("retrieved_instances", 0),
        "expected_instances": job.get("expected_instances"),
    })


@burn_bp.route("/download/<job_id:str>", methods=["GET"])
async def download_iso(request: Request, job_id: str):
    job = active_jobs.get(job_id)
    if not job:
        return json_response({"error": "Job not found"}, status=404)

    if job["status"] != "complete" or not job["output_path"]:
        return json_response({"error": "ISO not ready yet"}, status=409)

    iso_path = job["output_path"]
    if not os.path.exists(iso_path):
        return json_response({"error": "ISO file not found on server"}, status=404)

    filename = job["filename"] or "dicom_images.iso"

    return await file_stream(
        iso_path,
        mime_type="application/x-iso9660-image",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@burn_bp.route("/cleanup/<job_id:str>", methods=["POST"])
async def cleanup_job(request: Request, job_id: str):
    job = active_jobs.get(job_id)
    if not job:
        return json_response({"error": "Job not found"}, status=404)

    if job["output_path"] and os.path.exists(job["output_path"]):
        try:
            os.remove(job["output_path"])
            logger.info("Cleaned up ISO: %s", job["output_path"])
        except OSError as e:
            logger.warning("Failed to clean up ISO: %s", e)

    del active_jobs[job_id]
    job_locks.pop(job_id, None)
    return json_response({"status": "cleaned"})


async def _run_build_job(job_id: str, burn_req: BurnRequest, node: dict):
    job = active_jobs[job_id]
    job_lock = job_locks[job_id]
    try:
        job["status"] = "retrieving"
        job["message"] = "Retrieving DICOM files from PACS... (0)"
        job["progress"] = 0.05

        orthanc_user, orthanc_password = config.orthanc_http_credentials(node)
        builder = CdBuilderService(
            local_ae=config.local_ae_title,
            local_port=config.local_port,
            remote_ae=node["ae_title"],
            remote_host=node["host"],
            remote_port=node["port"],
            temp_dir=config.TEMP_DIR,
            viewer_path=config.OHIF_VIEWER_PATH,
            launcher_path=config.LAUNCHER_PATH,
            orthanc_url=node.get("orthanc_url", ""),
            orthanc_user=orthanc_user,
            orthanc_password=orthanc_password,
        )

        expected_instances = burn_req.expected_instances or 0

        def on_instance_retrieved(total_retrieved: int) -> None:
            with job_lock:
                job["retrieved_instances"] = total_retrieved
                if expected_instances > 0:
                    ratio = min(total_retrieved / expected_instances, 1.0)
                    retrieval_progress = 0.05 + (0.75 * ratio)
                    job["message"] = (
                        f"Retrieving DICOM files from PACS... "
                        f"({total_retrieved}/{expected_instances})"
                    )
                else:
                    # Unknown total: keep moving slowly so users see activity.
                    retrieval_progress = min(0.8, 0.05 + (total_retrieved * 0.001))
                    job["message"] = (
                        f"Retrieving DICOM files from PACS... "
                        f"({total_retrieved} retrieved)"
                    )
                job["progress"] = retrieval_progress

        work_dir = await builder.retrieve_studies(
            burn_req.studies,
            series_filter=burn_req.series,
            on_instance_retrieved=on_instance_retrieved,
        )

        job["status"] = "building"
        job["message"] = "Building ISO image with viewer and launchers..."
        job["progress"] = 0.9

        output_path = await builder.build_iso(
            work_dir=work_dir,
            patient_name=burn_req.patient_name,
            patient_id=burn_req.patient_id,
            include_viewer=burn_req.include_viewer,
        )

        filename = os.path.basename(output_path)

        job["status"] = "complete"
        job["message"] = "ISO ready — download it and burn to CD on your PC"
        job["progress"] = 1.0
        job["output_path"] = output_path
        job["filename"] = filename

    except Exception as e:
        job["status"] = "error"
        job["message"] = str(e)
        job["progress"] = 0.0

import os
import uuid
import logging
from pathlib import Path
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


def _resolve_backend_relative(path_str: str) -> str:
    """Resolve paths like ../cd_template/viewer relative to the backend package root."""
    p = Path(path_str)
    if p.is_absolute():
        return str(p.resolve())
    backend_root = Path(__file__).resolve().parent.parent
    return str((backend_root / p).resolve())


def _resolve_kpacs_template_path(path_str: str) -> str:
    """Resolve K-PACS template dir.

    Local dev: backend lives in repo/backend, so ../cd_template/kpacs works.
    Docker (backend/Dockerfile): app root is /app, so ../cd_template/kpacs wrongly becomes
    /cd_template/kpacs; the compose volume mounts templates at /app/cd_template/kpacs instead.
    """
    backend_root = Path(__file__).resolve().parent.parent
    raw = Path((path_str or ".").strip())
    candidates: list[str] = []

    if raw.is_absolute():
        candidates.append(str(raw.resolve()))
    else:
        candidates.append(str((backend_root / raw).resolve()))

    candidates.append(str((backend_root / "cd_template" / "kpacs").resolve()))

    seen: set[str] = set()
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        if os.path.isdir(c):
            logger.info("Using K-PACS template directory: %s", c)
            return c

    return candidates[0]


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
        "kpacs_output_path": None,
        "kpacs_filename": None,
        "kpacs_error": None,
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

    kpacs_path = job.get("kpacs_output_path")
    return json_response({
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "message": job["message"],
        "filename": job["filename"],
        "download_ready": job["status"] == "complete" and job["output_path"] is not None,
        "kpacs_filename": job.get("kpacs_filename"),
        "kpacs_download_ready": job["status"] == "complete" and bool(kpacs_path),
        "kpacs_error": job.get("kpacs_error"),
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


@burn_bp.route("/download-kpacs/<job_id:str>", methods=["GET"])
async def download_kpacs_iso(request: Request, job_id: str):
    job = active_jobs.get(job_id)
    if not job:
        return json_response({"error": "Job not found"}, status=404)

    if job["status"] != "complete":
        return json_response({"error": "K-PACS ISO not ready yet"}, status=409)

    kpacs_path = job.get("kpacs_output_path")
    if not kpacs_path or not os.path.exists(kpacs_path):
        err = job.get("kpacs_error") or "K-PACS ISO was not produced for this job"
        return json_response({"error": err}, status=404)

    filename = job.get("kpacs_filename") or "kpacs_disc.iso"

    return await file_stream(
        kpacs_path,
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

    for label, path_key in (
        ("OHIF ISO", "output_path"),
        ("K-PACS ISO", "kpacs_output_path"),
    ):
        path = job.get(path_key)
        if path and os.path.exists(path):
            try:
                os.remove(path)
                logger.info("Cleaned up %s: %s", label, path)
            except OSError as e:
                logger.warning("Failed to clean up %s: %s", label, e)

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
        kpacs_tpl = _resolve_kpacs_template_path(config.KPACS_TEMPLATE_PATH)
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
            kpacs_template_path=kpacs_tpl,
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
        job["output_path"] = output_path
        job["filename"] = filename

        if burn_req.include_kpacs:
            job["message"] = "Building K-PACS disc image (DICOMDIR + viewer)..."
            job["progress"] = 0.95
            try:
                kpacs_path = await builder.build_kpacs_iso(
                    work_dir=work_dir,
                    patient_name=burn_req.patient_name,
                    patient_id=burn_req.patient_id,
                )
                job["kpacs_output_path"] = kpacs_path
                job["kpacs_filename"] = os.path.basename(kpacs_path)
                job["kpacs_error"] = None
            except Exception as kpacs_exc:
                logger.exception("K-PACS ISO build failed")
                job["kpacs_output_path"] = None
                job["kpacs_filename"] = None
                job["kpacs_error"] = str(kpacs_exc)
        else:
            job["kpacs_error"] = None

        job["status"] = "complete"
        job["progress"] = 1.0
        if job.get("kpacs_error"):
            job["message"] = (
                "OHIF ISO is ready below. K-PACS ISO failed — see the message under "
                "the K-PACS download button."
            )
        elif burn_req.include_kpacs and job.get("kpacs_output_path"):
            job["message"] = (
                "Both disc images are ready: OHIF viewer ISO and K-PACS layout ISO "
                "(download below)."
            )
        else:
            job["message"] = "ISO ready — download it and burn to CD on your PC"

    except Exception as e:
        job["status"] = "error"
        job["message"] = str(e)
        job["progress"] = 0.0

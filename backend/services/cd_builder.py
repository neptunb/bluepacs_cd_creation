import os
import shutil
import logging
import uuid
import hashlib
from pathlib import Path
from typing import Optional

import pycdlib

from services.dicom_retrieve import DicomRetrieveService

logger = logging.getLogger(__name__)


def _iso_component(name: str, max_len: int = 30) -> str:
    """Return a deterministic ISO9660-safe path component."""
    cleaned = "".join(ch for ch in name.upper() if ch.isalnum() or ch in ("_", "-"))
    if not cleaned:
        cleaned = "X"
    if len(cleaned) <= max_len:
        return cleaned
    digest = hashlib.sha1(cleaned.encode("utf-8")).hexdigest()[:8].upper()
    head = cleaned[: max_len - 9]
    return f"{head}_{digest}"


def _iso_path_from_rel(rel_path: str) -> str:
    parts = [p for p in rel_path.replace("\\", "/").split("/") if p and p != "."]
    safe = [_iso_component(p) for p in parts]
    if not safe:
        return "/"
    return "/" + "/".join(safe)


class CdBuilderService:
    """Builds a CD/DVD ISO image containing DICOM files, OHIF viewer, and launchers."""

    def __init__(
        self,
        local_ae: str,
        local_port: int,
        remote_ae: str,
        remote_host: str,
        remote_port: int,
        temp_dir: str,
        viewer_path: str,
        launcher_path: str,
        orthanc_url: str = "",
        orthanc_user: str = "",
        orthanc_password: str = "",
    ):
        self.retriever = DicomRetrieveService(
            local_ae=local_ae,
            local_port=local_port,
            remote_ae=remote_ae,
            remote_host=remote_host,
            remote_port=remote_port,
            orthanc_url=orthanc_url,
            orthanc_user=orthanc_user,
            orthanc_password=orthanc_password,
        )
        self.temp_dir = temp_dir
        self.viewer_path = viewer_path
        self.launcher_path = launcher_path

    async def retrieve_studies(
        self,
        study_uids: list[str],
        series_filter: Optional[list[str]] = None,
    ) -> str:
        work_dir = os.path.join(self.temp_dir, str(uuid.uuid4()))
        study_dir = os.path.join(work_dir, "STUDY")
        os.makedirs(study_dir, exist_ok=True)
        total_files = 0
        per_study_counts: dict[str, int] = {}

        for study_uid in study_uids:
            output = os.path.join(study_dir, study_uid)
            count = await self.retriever.retrieve_study(
                study_instance_uid=study_uid,
                output_dir=output,
                series_filter=series_filter,
            )
            total_files += count
            per_study_counts[study_uid] = count
            logger.info("Retrieved %d files for study %s", count, study_uid)

        if total_files <= 0:
            details = ", ".join(f"{k}:{v}" for k, v in per_study_counts.items())
            raise RuntimeError(
                "No DICOM instances were retrieved from PACS. "
                f"Per-study counts: {details}. "
                "Check selected IDs, Orthanc permissions, and study availability."
            )

        return work_dir

    async def build_iso(
        self,
        work_dir: str,
        patient_name: str,
        patient_id: str,
        include_viewer: bool = True,
    ) -> str:
        if include_viewer:
            viewer_dest = os.path.join(work_dir, "viewer")
            if os.path.exists(self.viewer_path):
                shutil.copytree(self.viewer_path, viewer_dest, dirs_exist_ok=True)

            if os.path.exists(self.launcher_path):
                for launcher in ["windows_view.exe", "macos_view", "linux_view"]:
                    src = os.path.join(self.launcher_path, launcher)
                    if os.path.exists(src):
                        dest = os.path.join(work_dir, launcher)
                        shutil.copy2(src, dest)

            autorun = os.path.join(work_dir, "autorun.inf")
            with open(autorun, "w") as f:
                f.write("[AutoRun]\n")
                f.write("open=windows_view.exe\n")
                f.write(f"label=DICOM Images - {patient_name}\n")

            readme = os.path.join(work_dir, "README.txt")
            with open(readme, "w") as f:
                f.write(f"DICOM Images CD - {patient_name} ({patient_id})\n")
                f.write("=" * 50 + "\n\n")
                f.write("To view your medical images:\n\n")
                f.write("  Windows: Double-click windows_view.exe\n")
                f.write("  macOS:   Double-click macos_view\n")
                f.write("  Linux:   Run ./linux_view in terminal\n\n")
                f.write("A browser window will open with the image viewer.\n")
                f.write("Close the browser and terminal when finished.\n")

        safe_name = "".join(c for c in patient_name if c.isalnum() or c in " _-")[:32]
        iso_filename = f"DICOM_{safe_name}_{patient_id}.iso"
        iso_path = os.path.join(self.temp_dir, iso_filename)

        _create_iso(work_dir, iso_path, patient_name)

        return iso_path


def _create_iso(source_dir: str, iso_path: str, volume_label: str):
    iso = pycdlib.PyCdlib()
    iso.new(
        interchange_level=3,
        joliet=3,
        rock_ridge="1.09",
        vol_ident=_iso_component(volume_label, max_len=32),
    )

    for root, dirs, files in os.walk(source_dir):
        rel_root = os.path.relpath(root, source_dir)

        if rel_root != ".":
            iso_dir = _iso_path_from_rel(rel_root)
            joliet_dir = "/" + rel_root.replace(os.sep, "/")
            rr_name = os.path.basename(rel_root)[:128]
            try:
                iso.add_directory(
                    iso_path=iso_dir,
                    joliet_path=joliet_dir,
                    rr_name=rr_name,
                )
            except Exception as e:
                logger.warning("Could not add directory %s to ISO: %s", rel_root, e)
                continue

        for filename in files:
            filepath = os.path.join(root, filename)
            rel_path = os.path.relpath(filepath, source_dir)

            iso_name = _iso_path_from_rel(rel_path)
            joliet_name = "/" + rel_path.replace(os.sep, "/")
            rr_name = filename[:128]

            try:
                iso.add_file(
                    filepath,
                    iso_path=f"{iso_name};1",
                    joliet_path=joliet_name,
                    rr_name=rr_name,
                )
            except Exception as e:
                logger.warning("Could not add file %s to ISO: %s", filepath, e)

    iso.write(iso_path)
    iso.close()

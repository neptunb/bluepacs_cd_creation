import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

# Holds only the local BLUEPACS_CD listener identity (ae_title + port).
# The remote node list is no longer stored here — it lives in Ultramar's
# `dicom_modalities` table and is fetched via `services.ultramar_nodes`.
NODES_FILE = Path(__file__).parent / "dicom_nodes.json"


def _load_local() -> dict:
    with open(NODES_FILE, "r") as f:
        return json.load(f)


class Config:
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8100"))
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"

    TEMP_DIR: str = os.getenv("TEMP_DIR", "/tmp/bluepacs_cd")
    # Standalone OHIF viewer: the self-contained macos_view / linux_view /
    # windows_view.exe binaries plus the study/ placeholder folder. Populate
    # with `./scripts/sync_standalone.sh` (see cd_template/standalone/README.md).
    STANDALONE_VIEWER_PATH: str = os.getenv(
        "STANDALONE_VIEWER_PATH", "../cd_template/standalone"
    )
    # K-PACS Lite viewer binaries and config (no DICOM/DICOMDIR — those are generated per job).
    KPACS_TEMPLATE_PATH: str = os.getenv("KPACS_TEMPLATE_PATH", "../cd_template/kpacs")

    # When Orthanc /tools/find returns 0 (e.g. MySQL index), "recent studies" uses GET /studies + metadata.
    ORTHANC_RECENT_STUDIES_MAX_SCAN: int = int(
        os.getenv("ORTHANC_RECENT_STUDIES_MAX_SCAN", "4000")
    )
    ORTHANC_RECENT_STUDIES_CONCURRENCY: int = int(
        os.getenv("ORTHANC_RECENT_STUDIES_CONCURRENCY", "32")
    )

    # Ultramar phpapi: session + P_CAN_USE_CD_CREATION (empty URL = skip auth for local dev)
    CD_AUTH_VALIDATE_URL: str = (os.getenv("CD_AUTH_VALIDATE_URL") or "").strip()

    # Ultramar phpapi: returns DICOM nodes from the dicom_modalities DB table
    # (empty URL = use ULTRAMAR_NODES_SAMPLE in dev mode).
    ULTRAMAR_NODES_URL: str = (os.getenv("ULTRAMAR_NODES_URL") or "").strip()

    # Optional: path to a local JSON fallback (list of nodes) used only when
    # ULTRAMAR_NODES_URL is empty. Defaults to `backend/dicom_nodes.sample.json`
    # if it exists; otherwise an empty list.
    ULTRAMAR_NODES_SAMPLE: str = (
        os.getenv("ULTRAMAR_NODES_SAMPLE")
        or str(Path(__file__).parent / "dicom_nodes.sample.json")
    ).strip()

    @staticmethod
    def orthanc_http_credentials(node: dict) -> tuple[str, str]:
        """HTTP Basic for Orthanc REST. Environment ORTHANC_USER / ORTHANC_PASSWORD override node JSON."""
        u = (os.getenv("ORTHANC_USER") or "").strip()
        p = (os.getenv("ORTHANC_PASSWORD") or "").strip()
        if not u:
            u = (node.get("orthanc_user") or "").strip()
        if not p:
            p = (node.get("orthanc_password") or "").strip()
        return u, p

    @property
    def local_ae_title(self) -> str:
        return _load_local()["local"]["ae_title"]

    @property
    def local_port(self) -> int:
        return _load_local()["local"]["port"]

    @staticmethod
    def dicom_remote_ae(node: dict) -> str:
        """Called AE for C-ECHO / C-FIND / C-MOVE when different from node id (e.g. ORTHANC)."""
        return (node.get("remote_dicom_ae") or node["ae_title"]).strip()


config = Config()

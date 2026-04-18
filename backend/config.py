import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

NODES_FILE = Path(__file__).parent / "dicom_nodes.json"


def _load_nodes() -> dict:
    with open(NODES_FILE, "r") as f:
        return json.load(f)


def _save_nodes(data: dict) -> None:
    with open(NODES_FILE, "w") as f:
        json.dump(data, f, indent=2)


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
        return _load_nodes()["local"]["ae_title"]

    @property
    def local_port(self) -> int:
        return _load_nodes()["local"]["port"]

    @staticmethod
    def get_nodes() -> list[dict]:
        return _load_nodes()["nodes"]

    @staticmethod
    def dicom_remote_ae(node: dict) -> str:
        """Called AE for C-ECHO / C-FIND / C-MOVE when different from node id (e.g. ORTHANC)."""
        return (node.get("remote_dicom_ae") or node["ae_title"]).strip()

    @staticmethod
    def get_node(ae_title: str) -> dict | None:
        for node in _load_nodes()["nodes"]:
            if node["ae_title"] == ae_title:
                return node
        return None

    @staticmethod
    def add_node(node: dict) -> None:
        data = _load_nodes()
        for existing in data["nodes"]:
            if existing["ae_title"] == node["ae_title"]:
                raise ValueError(f"Node {node['ae_title']} already exists")
        data["nodes"].append(node)
        _save_nodes(data)

    @staticmethod
    def update_node(ae_title: str, updates: dict) -> None:
        data = _load_nodes()
        for i, existing in enumerate(data["nodes"]):
            if existing["ae_title"] == ae_title:
                data["nodes"][i] = {**existing, **updates}
                _save_nodes(data)
                return
        raise ValueError(f"Node {ae_title} not found")

    @staticmethod
    def remove_node(ae_title: str) -> None:
        data = _load_nodes()
        data["nodes"] = [n for n in data["nodes"] if n["ae_title"] != ae_title]
        _save_nodes(data)


config = Config()

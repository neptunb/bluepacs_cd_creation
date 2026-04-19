import asyncio
import os
import stat
import shutil
import logging
import uuid
import hashlib
import unicodedata
import subprocess
from pathlib import Path
from typing import Callable, Optional

import pydicom
import pycdlib
from pycdlib import pycdlibexception

from constants.disc_layout import (
    OHIF_DISC_IMAGE_SUBDIR,
    WORKSPACE_DICOM_SUBDIR,
    WORKSPACE_STUDY_ZIP_SUBDIR,
)
from services.dicom_retrieve import DicomRetrieveService

logger = logging.getLogger(__name__)


def _iso_component(name: str, max_len: int = 30) -> str:
    """Return a deterministic ISO9660-safe path component.

    pycdlib enforces strict ISO9660 names (A–Z, 0–9, underscore only). Hyphens and
    dots in the source filename must not appear here; Joliet carries readable names.
    """
    ascii_name = _ascii_safe_text(name).upper()
    cleaned = "".join(ch for ch in ascii_name if ch.isalnum() or ch == "_")
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


# Characters unsafe in Joliet / Windows paths (and path separators).
_JOLIET_BAD = frozenset(':*?"<>|\\\x00')


def _joliet_segment(name: str, max_len: int = 64) -> str:
    """One path component for Joliet (Windows-friendly listing); keeps .exe, .dll, etc."""
    n = unicodedata.normalize("NFKC", name or "").strip() or "X"
    out: list[str] = []
    for ch in n:
        if ch in _JOLIET_BAD or ord(ch) < 32:
            out.append("_")
        else:
            out.append(ch)
    n = "".join(out).strip() or "X"
    if len(n) > max_len:
        root, ext = os.path.splitext(n)
        if ext and 1 <= len(ext) <= 16:
            room = max(1, max_len - len(ext))
            n = (root[:room] + ext)[:max_len]
        else:
            n = n[:max_len]
    return n


def _joliet_path_from_rel(rel_path: str) -> str:
    """Absolute Joliet path with readable names (Finder / Explorer), unlike ISO9660-only mangling."""
    parts = [p for p in rel_path.replace("\\", "/").split("/") if p and p != "."]
    if not parts:
        return "/"
    return "/" + "/".join(_joliet_segment(p) for p in parts)


def _ascii_safe_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    return ascii_text.strip() or "UNKNOWN"


def _rock_ridge_file_mode(filepath: str) -> int:
    """POSIX mode for Rock Ridge entries; Unix launchers must be 755 or Finder opens them as documents."""
    base = os.path.basename(filepath)
    if base in ("macos_view", "linux_view"):
        return 0o755
    try:
        return stat.S_IMODE(os.stat(filepath).st_mode)
    except OSError:
        return 0o644


def _kpacs_launcher_exe_name(template_dir: str) -> str:
    try:
        names = sorted(
            n for n in os.listdir(template_dir) if n.lower().endswith(".exe")
        )
    except OSError as e:
        raise RuntimeError(f"Cannot read K-PACS template directory: {template_dir}") from e
    if not names:
        raise RuntimeError(
            f"K-PACS template has no .exe launcher (expected under {template_dir})"
        )
    return names[0]


def _write_kpacs_autorun(staging_dir: str, launcher_exe: str) -> None:
    path = os.path.join(staging_dir, "autorun.inf")
    with open(path, "w", encoding="utf-8") as f:
        f.write("[autorun]\n")
        f.write(f"open={launcher_exe}\n")


def _write_standalone_autorun(staging_dir: str, patient_name: str) -> None:
    """AutoRun descriptor when windows_view.exe is on the disc (Windows only — other OSes ignore it)."""
    path = os.path.join(staging_dir, "autorun.inf")
    patient_name_ascii = _ascii_safe_text(patient_name)
    with open(path, "w", encoding="utf-8") as f:
        f.write("[AutoRun]\n")
        f.write("open=windows_view.exe\n")
        f.write(f"label=DICOM Images - {patient_name_ascii}\n")
        f.write("icon=windows_view.exe,0\n")
        f.write("action=Open DICOM Viewer\n")


def _write_patient_readme(
    staging_dir: str,
    patient_name: str,
    patient_id: str,
    include_macos_launcher: bool = True,
    include_windows_launcher: bool = True,
    include_linux_launcher: bool = False,
) -> None:
    """Patient-facing README explaining how to open each included standalone launcher."""
    readme = os.path.join(staging_dir, "README.txt")
    sep = "=" * 50
    with open(readme, "w", encoding="utf-8") as f:
        f.write(f"DICOM Images CD - {patient_name} ({patient_id})\n")
        f.write(sep + "\n\n")
        f.write("This CD contains your medical images along with a portable viewer\n")
        f.write("that requires no installation.\n\n")
        f.write("HOW TO VIEW YOUR IMAGES\n")
        f.write("-" * 50 + "\n")
        if include_windows_launcher:
            f.write("  Windows: Double-click  windows_view.exe\n")
        if include_macos_launcher:
            f.write("  macOS:   Double-click  macos_view\n")
            f.write("           (right-click > Open the first time)\n")
        if include_linux_launcher:
            f.write("  Linux:   Open a terminal here and run:  ./linux_view\n")
        f.write("\nA web browser window opens automatically showing your images.\n\n")
        if include_macos_launcher:
            f.write("macOS security (Gatekeeper)\n")
            f.write("-" * 50 + "\n")
            f.write(
                "If macOS says the app cannot be verified, that is normal for an\n"
                "unsigned viewer. Try in order:\n"
                "  1) Right-click macos_view, choose Open, then click Open again.\n"
                "  2) System Settings > Privacy & Security > Open Anyway.\n"
                "  3) Terminal: xattr -cr '/path/to/macos_view' then try again.\n"
                "If TextEdit opens with random characters instead, run in Terminal:\n"
                "  chmod +x macos_view && ./macos_view\n\n"
            )
        f.write("CONTENTS\n")
        f.write("-" * 50 + "\n")
        f.write("  study/            Your DICOM image files\n")
        if include_windows_launcher:
            f.write("  windows_view.exe  Windows launcher (embedded OHIF viewer)\n")
        if include_macos_launcher:
            f.write("  macos_view        macOS launcher (embedded OHIF viewer)\n")
        if include_linux_launcher:
            f.write("  linux_view        Linux launcher (embedded OHIF viewer)\n")
        f.write("\n")
        f.write("CLOSING\n")
        f.write("-" * 50 + "\n")
        f.write("Close the browser tab, then the terminal/command window that\n")
        f.write("appeared when the viewer started.\n\n")
        f.write(sep + "\n")


def _dicom_instance_sort_key(path: Path) -> tuple:
    """Sort key for instances: InstanceNumber when present, else SOPInstanceUID, else filename."""
    try:
        ds = pydicom.dcmread(path, stop_before_pixels=True, force=True)
        inst = getattr(ds, "InstanceNumber", None)
        if inst is not None:
            s = str(inst).strip()
            if s.isdigit():
                return (0, int(s), "")
            try:
                return (0, int(float(s)), "")
            except ValueError:
                return (1, 0, s)
        sop = str(getattr(ds, "SOPInstanceUID", "") or "")
        return (2, 0, sop)
    except Exception:
        return (3, 0, path.name)


def _reorganize_dicom_tree_for_interchange(dicom_root: str) -> None:
    """Rewrite DICOM/studyUID/seriesUID/*.dcm into S#####/SER#####/I##### for dcmmkdir (ISO 9660)."""
    root = Path(dicom_root)
    study_paths = sorted([p for p in root.iterdir() if p.is_dir()], key=lambda p: p.name)
    if not study_paths:
        raise RuntimeError(
            "No study subfolders under DICOM; cannot build K-PACS interchange layout"
        )

    parent = root.parent
    tmp = parent / f"_dicom_interchange_{uuid.uuid4().hex}"
    tmp.mkdir()

    try:
        for si, study_path in enumerate(study_paths, start=1):
            sdir = tmp / f"S{si:05d}"
            series_paths = sorted(
                [p for p in study_path.iterdir() if p.is_dir()],
                key=lambda p: p.name,
            )
            if not series_paths:
                ser_dest = sdir / "SER00001"
                ser_dest.mkdir(parents=True, exist_ok=True)
                files = sorted(
                    [p for p in study_path.iterdir() if p.is_file()],
                    key=_dicom_instance_sort_key,
                )
                for ii, fp in enumerate(files, start=1):
                    dest = ser_dest / f"I{ii:05d}"
                    shutil.copy2(fp, dest)
                continue

            for seri, ser_path in enumerate(series_paths, start=1):
                ser_name = f"SER{seri:05d}"
                if len(ser_name) > 8:
                    raise RuntimeError(
                        "Too many series in one study for K-PACS interchange naming (max 99999)"
                    )
                ser_dest = sdir / ser_name
                ser_dest.mkdir(parents=True, exist_ok=True)
                files = sorted(
                    [p for p in ser_path.iterdir() if p.is_file()],
                    key=_dicom_instance_sort_key,
                )
                for ii, fp in enumerate(files, start=1):
                    dest = ser_dest / f"I{ii:05d}"
                    shutil.copy2(fp, dest)

        shutil.rmtree(dicom_root)
        shutil.move(str(tmp), str(dicom_root))
        logger.info(
            "Reorganized %d stud(ies) under %s for DICOMDIR interchange naming",
            len(study_paths),
            dicom_root,
        )
    except BaseException:
        if tmp.exists():
            shutil.rmtree(tmp, ignore_errors=True)
        raise


def _copy_kpacs_template_files(template_dir: str, staging_dir: str) -> None:
    """Copy root-level template files (no subdirs) and write autorun.inf for the launcher .exe.

    K-Pacs Lite files in the template are third-party legacy software; redistribution is the site's responsibility.
    """
    launcher = _kpacs_launcher_exe_name(template_dir)
    for name in os.listdir(template_dir):
        src = os.path.join(template_dir, name)
        if not os.path.isfile(src):
            continue
        shutil.copy2(src, os.path.join(staging_dir, name))
    _write_kpacs_autorun(staging_dir, launcher)


def _generate_dicomdir_dcmtk(staging_dir: str) -> None:
    dcmmkdir = shutil.which("dcmmkdir")
    if not dcmmkdir:
        raise RuntimeError(
            "K-PACS ISO requires a root DICOMDIR. Install DCMTK and ensure `dcmmkdir` is on "
            "PATH (e.g. `brew install dcmtk` on macOS, `apt install dcmtk` on Debian/Ubuntu). "
            "If you run the backend in Docker, rebuild the image so the Dockerfile can install "
            "the `dcmtk` package."
        )
    dicom_root = os.path.join(staging_dir, WORKSPACE_DICOM_SUBDIR)
    if not os.path.isdir(dicom_root):
        raise RuntimeError("Internal error: staging DICOM folder missing for DICOMDIR")

    cmd = [
        dcmmkdir,
        "+r",
        "+I",
        "-Nxc",
        "+D",
        "DICOMDIR",
        WORKSPACE_DICOM_SUBDIR,
    ]
    proc = subprocess.run(
        cmd,
        cwd=staging_dir,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "").strip() or "no stderr"
        raise RuntimeError(f"dcmmkdir failed (exit {proc.returncode}): {detail}")


STANDALONE_LAUNCHERS: tuple[str, ...] = (
    "macos_view",
    "linux_view",
    "windows_view.exe",
)

MACOS_LAUNCHER = "macos_view"
WINDOWS_LAUNCHER = "windows_view.exe"
LINUX_LAUNCHER = "linux_view"


class CdBuilderService:
    """Builds a CD/DVD ISO image containing DICOM files and the standalone OHIF viewer."""

    def __init__(
        self,
        local_ae: str,
        local_port: int,
        remote_ae: str,
        remote_host: str,
        remote_port: int,
        temp_dir: str,
        standalone_viewer_path: str,
        orthanc_url: str = "",
        orthanc_user: str = "",
        orthanc_password: str = "",
        kpacs_template_path: str = "",
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
        self.standalone_viewer_path = standalone_viewer_path
        self.kpacs_template_path = kpacs_template_path

    async def retrieve_studies(
        self,
        study_uids: list[str],
        series_filter: Optional[list[str]] = None,
        on_instance_retrieved: Optional[Callable[[int], None]] = None,
        images_subdir: str = WORKSPACE_DICOM_SUBDIR,
    ) -> str:
        """Retrieve instances under ``work_dir/<images_subdir>/<StudyInstanceUID>/...``.

        Default ``WORKSPACE_DICOM_SUBDIR`` keeps K-PACS and OHIF ISO layouts unchanged. Use
        ``WORKSPACE_STUDY_ZIP_SUBDIR`` for a STUDY-folder ZIP download without modifying
        K-PACS code paths (they still expect ``DICOM`` from the default retrieve).
        """
        if images_subdir not in (WORKSPACE_DICOM_SUBDIR, WORKSPACE_STUDY_ZIP_SUBDIR):
            raise ValueError(
                "images_subdir must be "
                f"{WORKSPACE_DICOM_SUBDIR!r} or {WORKSPACE_STUDY_ZIP_SUBDIR!r}"
            )

        work_dir = os.path.join(self.temp_dir, str(uuid.uuid4()))
        root_dir = os.path.join(work_dir, images_subdir)
        os.makedirs(root_dir, exist_ok=True)
        total_files = 0
        per_study_counts: dict[str, int] = {}

        for study_uid in study_uids:
            output = os.path.join(root_dir, study_uid)
            prior_total = total_files
            count = await self.retriever.retrieve_study(
                study_instance_uid=study_uid,
                output_dir=output,
                series_filter=series_filter,
                on_instance_retrieved=(
                    (
                        lambda study_count, base=prior_total: on_instance_retrieved(
                            base + study_count
                        )
                    )
                    if on_instance_retrieved
                    else None
                ),
            )
            total_files += count
            per_study_counts[study_uid] = count
            logger.info("Retrieved %d files for study %s", count, study_uid)

        if total_files <= 0:
            details = ", ".join(f"{k}:{v}" for k, v in per_study_counts.items())
            raise RuntimeError(
                "No DICOM instances were retrieved from PACS. "
                f"Per-study counts: {details}. "
                "If the archive is Orthanc, add \"orthanc_url\": \"http://<host>:8042\" to "
                "that node in dicom_nodes.json for REST retrieval. "
                "Otherwise check AE titles, ports, firewall, and C-MOVE reachability."
            )

        return work_dir

    async def build_iso(
        self,
        work_dir: str,
        patient_name: str,
        patient_id: str,
        include_viewer: bool = True,
        include_macos_launcher: bool = True,
        include_windows_launcher: bool = True,
        include_linux_launcher: bool = False,
    ) -> str:
        """Build the patient CD ISO with the standalone OHIF viewer.

        Layout on disc (Joliet names):
            ./macos_view               standalone launcher (macOS), optional
            ./linux_view               standalone launcher (Linux), optional
            ./windows_view.exe         standalone launcher (Windows), optional
            ./autorun.inf              Windows AutoRun (only if windows_view.exe included)
            ./README.txt               patient-facing instructions
            ./study/<StudyInstanceUID>/<SeriesInstanceUID>/*.dcm
            (folder name matches ``OHIF_DISC_IMAGE_SUBDIR`` in ``constants.disc_layout``).

        The retrieved ``work_dir/DICOM`` tree is moved (``os.rename``) to
        ``staging/study`` so we avoid a 2GB+ physical copy on large studies,
        and restored afterwards so ``build_kpacs_iso`` still finds it. All
        blocking I/O and the ISO write run in a worker thread so the Sanic
        event loop keeps responding to ``/status`` polls while the disc is
        assembled.

        ``include_viewer=False`` produces a data-only disc (no binaries, no autorun).
        """
        dicom_src = os.path.join(work_dir, WORKSPACE_DICOM_SUBDIR)
        if not os.path.isdir(dicom_src):
            raise RuntimeError(
                "No DICOM folder found in work_dir; retrieval must run before build_iso"
            )

        if include_viewer:
            if not (
                include_macos_launcher
                or include_windows_launcher
                or include_linux_launcher
            ):
                raise RuntimeError(
                    "Select at least one viewer platform (macOS, Windows, and/or Linux)."
                )
            self._require_standalone_assets(
                include_macos_launcher=include_macos_launcher,
                include_windows_launcher=include_windows_launcher,
                include_linux_launcher=include_linux_launcher,
            )

        safe_name = "".join(
            c for c in _ascii_safe_text(patient_name) if c.isalnum() or c in " _-"
        )[:32]
        safe_patient_id = "".join(
            c for c in _ascii_safe_text(patient_id) if c.isalnum() or c in "_-"
        )[:32] or "UNKNOWNID"
        iso_filename = f"DICOM_{safe_name}_{safe_patient_id}.iso"
        iso_path = os.path.join(self.temp_dir, iso_filename)

        def _assemble_and_write() -> None:
            staging = os.path.join(self.temp_dir, f"ohif_stage_{uuid.uuid4()}")
            study_dest = os.path.join(staging, OHIF_DISC_IMAGE_SUBDIR)
            os.makedirs(staging, exist_ok=True)

            moved = False
            try:
                # Move the DICOM tree (same filesystem under TEMP_DIR → O(1) rename);
                # fall back to a full copy if the rename is rejected (e.g. separate mount).
                try:
                    os.rename(dicom_src, study_dest)
                    moved = True
                except OSError as e:
                    logger.warning(
                        "Could not rename %s -> %s (%s); falling back to copytree",
                        dicom_src, study_dest, e,
                    )
                    shutil.copytree(dicom_src, study_dest, symlinks=False)

                if include_viewer:
                    self._copy_standalone_launchers(
                        staging,
                        include_macos_launcher=include_macos_launcher,
                        include_windows_launcher=include_windows_launcher,
                        include_linux_launcher=include_linux_launcher,
                    )
                    if include_windows_launcher:
                        _write_standalone_autorun(staging, patient_name)
                    _write_patient_readme(
                        staging,
                        patient_name,
                        patient_id,
                        include_macos_launcher=include_macos_launcher,
                        include_windows_launcher=include_windows_launcher,
                        include_linux_launcher=include_linux_launcher,
                    )

                # No Rock Ridge: same as K-PACS ISO — macOS Finder often shows RR+Joliet
                # pycdlib images as an empty volume even though files exist (Windows sees
                # them). Unix launchers may need chmod +x once copied (see README.txt).
                _create_iso(staging, iso_path, patient_name, rock_ridge=None)
            finally:
                # Always put DICOM back so build_kpacs_iso (which reads work_dir/DICOM)
                # can run next even if ISO creation raised partway through.
                if moved and os.path.isdir(study_dest) and not os.path.exists(dicom_src):
                    try:
                        os.rename(study_dest, dicom_src)
                    except OSError as restore_exc:
                        logger.error(
                            "Could not restore DICOM from %s to %s: %s",
                            study_dest, dicom_src, restore_exc,
                        )
                if os.path.isdir(staging):
                    try:
                        shutil.rmtree(staging)
                    except OSError as e:
                        logger.warning("Could not remove OHIF staging %s: %s", staging, e)

        await asyncio.to_thread(_assemble_and_write)
        return iso_path

    def _require_standalone_assets(
        self,
        include_macos_launcher: bool = True,
        include_windows_launcher: bool = True,
        include_linux_launcher: bool = False,
    ) -> None:
        path = self.standalone_viewer_path
        if not path or not os.path.isdir(path):
            raise RuntimeError(
                "STANDALONE_VIEWER_PATH is not configured or does not exist: "
                f"{path or '(unset)'}. See cd_template/standalone/README.md and run "
                "./scripts/sync_standalone.sh."
            )
        required: list[str] = []
        if include_macos_launcher:
            required.append(MACOS_LAUNCHER)
        if include_windows_launcher:
            required.append(WINDOWS_LAUNCHER)
        if include_linux_launcher:
            required.append(LINUX_LAUNCHER)
        missing = [
            b for b in required
            if not os.path.isfile(os.path.join(path, b))
        ]
        if missing:
            raise RuntimeError(
                f"Standalone viewer folder {path} is missing binaries: "
                f"{', '.join(missing)}. Run ./scripts/sync_standalone.sh to populate it."
            )

    def _copy_standalone_launchers(
        self,
        staging_dir: str,
        include_macos_launcher: bool = True,
        include_windows_launcher: bool = True,
        include_linux_launcher: bool = False,
    ) -> None:
        names: list[str] = []
        if include_macos_launcher:
            names.append(MACOS_LAUNCHER)
        if include_windows_launcher:
            names.append(WINDOWS_LAUNCHER)
        if include_linux_launcher:
            names.append(LINUX_LAUNCHER)
        for name in names:
            src = os.path.join(self.standalone_viewer_path, name)
            dest = os.path.join(staging_dir, name)
            shutil.copy2(src, dest)
            if name in ("macos_view", "linux_view"):
                try:
                    os.chmod(dest, 0o755)
                except OSError as e:
                    logger.warning("chmod launcher %s: %s", dest, e)

    async def build_kpacs_iso(
        self,
        work_dir: str,
        patient_name: str,
        patient_id: str,
    ) -> str:
        """Build a second ISO with K-PACS layout: DICOM mirror, template viewer, DICOMDIR.

        Offloads the copytree + dcmmkdir + pycdlib write to a worker thread so the
        Sanic event loop keeps answering ``/status`` polls while the disc builds.
        """
        dicom_src = os.path.join(work_dir, WORKSPACE_DICOM_SUBDIR)
        if not os.path.isdir(dicom_src):
            raise RuntimeError("No DICOM folder found; cannot build K-PACS ISO")

        tpl = self.kpacs_template_path
        if not tpl or not os.path.isdir(tpl):
            raise RuntimeError(
                f"K-PACS template directory missing or invalid: {tpl or '(not configured)'}"
            )

        safe_name = "".join(
            c for c in _ascii_safe_text(patient_name) if c.isalnum() or c in " _-"
        )[:32]
        safe_patient_id = "".join(
            c for c in _ascii_safe_text(patient_id) if c.isalnum() or c in "_-"
        )[:32] or "UNKNOWNID"
        iso_filename = f"KPACS_{safe_name}_{safe_patient_id}.iso"
        iso_path = os.path.join(self.temp_dir, iso_filename)

        def _assemble_and_write() -> None:
            staging = os.path.join(self.temp_dir, f"kpacs_stage_{uuid.uuid4()}")
            try:
                dicom_dest = os.path.join(staging, WORKSPACE_DICOM_SUBDIR)
                shutil.copytree(dicom_src, dicom_dest, symlinks=False)
                _reorganize_dicom_tree_for_interchange(dicom_dest)
                _copy_kpacs_template_files(tpl, staging)
                _generate_dicomdir_dcmtk(staging)

                # No Rock Ridge: K-PACS is Windows-only; macOS Finder often shows
                # RR-heavy ISOs as empty.
                _create_iso(staging, iso_path, patient_name, rock_ridge=None)
            finally:
                if os.path.isdir(staging):
                    try:
                        shutil.rmtree(staging)
                    except OSError as e:
                        logger.warning("Could not remove K-PACS staging %s: %s", staging, e)

        await asyncio.to_thread(_assemble_and_write)
        return iso_path


def _create_iso(
    source_dir: str,
    iso_path: str,
    volume_label: str,
    rock_ridge: Optional[str] = None,
):
    """Write ISO9660 + Joliet; optional Rock Ridge (Unix execute bits — breaks Finder listing).

    Default is *no* Rock Ridge so macOS Finder lists the OHIF and K-PACS discs reliably.
    If you pass a Rock Ridge level string, some macOS versions show an empty volume in Finder.
    """
    source_dir = os.path.abspath(os.path.realpath(source_dir))
    if not os.path.isdir(source_dir):
        raise RuntimeError(f"ISO source path is not a directory: {source_dir}")

    expected_files = sum(len(files) for _, _, files in os.walk(source_dir))
    if expected_files == 0:
        raise RuntimeError(
            f"Refusing to build an empty ISO: no files under {source_dir}. "
            "Check retrieve paths and viewer template."
        )

    use_rr = bool(rock_ridge)
    iso = pycdlib.PyCdlib()
    iso.new(
        interchange_level=3,
        joliet=3,
        rock_ridge=rock_ridge,
        vol_ident=_iso_component(volume_label, max_len=32),
    )

    files_added = 0
    errors: list[str] = []
    dirs_registered: set[str] = set()

    for root, dirs, files in os.walk(source_dir):
        rel_root = os.path.relpath(root, source_dir)

        if rel_root != ".":
            iso_dir = _iso_path_from_rel(rel_root)
            joliet_dir = _joliet_path_from_rel(rel_root)
            if iso_dir not in dirs_registered:
                try:
                    if use_rr:
                        iso.add_directory(
                            iso_path=iso_dir,
                            joliet_path=joliet_dir,
                            rr_name=_ascii_safe_text(os.path.basename(rel_root))[:128],
                            file_mode=0o755,
                        )
                    else:
                        iso.add_directory(
                            iso_path=iso_dir,
                            joliet_path=joliet_dir,
                        )
                    dirs_registered.add(iso_dir)
                except pycdlibexception.PyCdlibInvalidInput as e:
                    el = str(e).lower()
                    if "already" in el or "duplicate" in el:
                        dirs_registered.add(iso_dir)
                    else:
                        msg = f"directory {rel_root}: {e}"
                        errors.append(msg)
                        logger.warning("Could not add directory %s to ISO: %s", rel_root, e)
                except Exception as e:
                    msg = f"directory {rel_root}: {e}"
                    errors.append(msg)
                    logger.warning("Could not add directory %s to ISO: %s", rel_root, e)
            # Never skip files here: a failed mkdir must not drop the whole subtree.

        for filename in files:
            filepath = os.path.join(root, filename)
            rel_path = os.path.relpath(filepath, source_dir)

            iso_name = _iso_path_from_rel(rel_path)
            joliet_name = _joliet_path_from_rel(rel_path)
            rr_name = _ascii_safe_text(filename)[:128]
            fmode = _rock_ridge_file_mode(filepath)

            try:
                if use_rr:
                    iso.add_file(
                        filepath,
                        iso_path=f"{iso_name};1",
                        joliet_path=joliet_name,
                        rr_name=rr_name,
                        file_mode=fmode,
                    )
                else:
                    iso.add_file(
                        filepath,
                        iso_path=f"{iso_name};1",
                        joliet_path=joliet_name,
                    )
                files_added += 1
            except pycdlibexception.PyCdlibInvalidInput as e:
                if joliet_name and "joliet" in str(e).lower():
                    try:
                        if use_rr:
                            iso.add_file(
                                filepath,
                                iso_path=f"{iso_name};1",
                                rr_name=rr_name,
                                file_mode=fmode,
                            )
                        else:
                            iso.add_file(filepath, iso_path=f"{iso_name};1")
                        files_added += 1
                    except Exception as e2:
                        msg = f"file {rel_path}: {e2}"
                        errors.append(msg)
                        logger.warning("Could not add file %s to ISO: %s", filepath, e2)
                else:
                    msg = f"file {rel_path}: {e}"
                    errors.append(msg)
                    logger.warning("Could not add file %s to ISO: %s", filepath, e)
            except Exception as e:
                msg = f"file {rel_path}: {e}"
                errors.append(msg)
                logger.warning("Could not add file %s to ISO: %s", filepath, e)

    if files_added == 0:
        tail = "\n".join(errors[:25]) if errors else "(no per-file errors recorded)"
        raise RuntimeError(
            f"ISO build added 0 of {expected_files} file(s). "
            f"First messages:\n{tail}"
        )
    if files_added < expected_files:
        logger.warning(
            "ISO incomplete: added %d of %d file(s); see prior warnings",
            files_added,
            expected_files,
        )

    iso.write(iso_path)
    iso.close()

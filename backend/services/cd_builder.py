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
    dicom_root = os.path.join(staging_dir, "DICOM")
    if not os.path.isdir(dicom_root):
        raise RuntimeError("Internal error: staging DICOM folder missing for DICOMDIR")

    cmd = [
        dcmmkdir,
        "+r",
        "+I",
        "-Nxc",
        "+D",
        "DICOMDIR",
        "DICOM",
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
        self.viewer_path = viewer_path
        self.launcher_path = launcher_path
        self.kpacs_template_path = kpacs_template_path

    async def retrieve_studies(
        self,
        study_uids: list[str],
        series_filter: Optional[list[str]] = None,
        on_instance_retrieved: Optional[Callable[[int], None]] = None,
        images_subdir: str = "DICOM",
    ) -> str:
        """Retrieve instances under ``work_dir/<images_subdir>/<StudyInstanceUID>/...``.

        Default ``DICOM`` keeps K-PACS and OHIF ISO layouts unchanged. Use ``STUDY`` for a
        STUDY-folder ZIP download without modifying K-PACS code paths (they still expect
        ``DICOM`` from the default retrieve).
        """
        if images_subdir not in ("DICOM", "STUDY"):
            raise ValueError("images_subdir must be 'DICOM' or 'STUDY'")

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
                        if launcher in ("macos_view", "linux_view"):
                            try:
                                os.chmod(dest, 0o755)
                            except OSError as e:
                                logger.warning("chmod launcher %s: %s", dest, e)

            autorun = os.path.join(work_dir, "autorun.inf")
            patient_name_ascii = _ascii_safe_text(patient_name)
            with open(autorun, "w", encoding="utf-8") as f:
                f.write("[AutoRun]\n")
                f.write("open=windows_view.exe\n")
                f.write(f"label=DICOM Images - {patient_name_ascii}\n")

            readme = os.path.join(work_dir, "README.txt")
            with open(readme, "w", encoding="utf-8") as f:
                f.write(f"DICOM Images CD - {patient_name} ({patient_id})\n")
                f.write("=" * 50 + "\n\n")
                f.write("To view your medical images:\n\n")
                f.write("  Windows: Double-click windows_view.exe\n")
                f.write("  macOS:   First open macos_view (see macOS note below)\n")
                f.write("  Linux:   Run ./linux_view in terminal\n\n")
                f.write(
                    "macOS security (Gatekeeper): If macOS says the app cannot be "
                    "verified or was not opened, that is normal for unsigned viewer "
                    "launchers. Try in order:\n"
                    "  1) Right-click macos_view, choose Open, then click Open again.\n"
                    "  2) System Settings -> Privacy & Security -> scroll down -> "
                    "Open Anyway (for macos_view).\n"
                    "  3) Terminal: xattr -cr '/path/to/macos_view' then open again "
                    "(removes quarantine if present).\n"
                    "If TextEdit (or another editor) opens and shows random characters, "
                    "the file was not treated as a program. Open Terminal, cd to the "
                    "folder that contains macos_view, then run:\n"
                    "  chmod +x macos_view && ./macos_view\n\n"
                )
                f.write("A browser window will open with the image viewer.\n")
                f.write("Close the browser and terminal when finished.\n\n")
                f.write("Where are the images on this disc?\n")
                f.write("  • This ISO uses the folder name DICOM/ (StudyInstanceUID subfolders).\n")
                f.write("  • There is no STUDY/ folder on this disc by design.\n")
                f.write("  • For a portable archive named STUDY/, use \"Download STUDY (ZIP)\" ")
                f.write("in the web app — that download is a .zip only, not an ISO.\n")

        safe_name = "".join(
            c for c in _ascii_safe_text(patient_name) if c.isalnum() or c in " _-"
        )[:32]
        safe_patient_id = "".join(
            c for c in _ascii_safe_text(patient_id) if c.isalnum() or c in "_-"
        )[:32] or "UNKNOWNID"
        iso_filename = f"DICOM_{safe_name}_{safe_patient_id}.iso"
        iso_path = os.path.join(self.temp_dir, iso_filename)

        # No Rock Ridge: same as K-PACS ISO — macOS Finder often shows RR+Joliet pycdlib
        # images as an empty volume even though files exist (Windows sees them). Unix
        # launchers may need chmod +x once copied (see README.txt on disc).
        _create_iso(work_dir, iso_path, patient_name, rock_ridge=None)

        return iso_path

    async def build_kpacs_iso(
        self,
        work_dir: str,
        patient_name: str,
        patient_id: str,
    ) -> str:
        """Build a second ISO with K-PACS layout: DICOM mirror, template viewer, DICOMDIR."""
        dicom_src = os.path.join(work_dir, "DICOM")
        if not os.path.isdir(dicom_src):
            raise RuntimeError("No DICOM folder found; cannot build K-PACS ISO")

        tpl = self.kpacs_template_path
        if not tpl or not os.path.isdir(tpl):
            raise RuntimeError(
                f"K-PACS template directory missing or invalid: {tpl or '(not configured)'}"
            )

        staging = os.path.join(self.temp_dir, f"kpacs_stage_{uuid.uuid4()}")
        try:
            dicom_dest = os.path.join(staging, "DICOM")
            shutil.copytree(dicom_src, dicom_dest, symlinks=False)
            _reorganize_dicom_tree_for_interchange(dicom_dest)
            _copy_kpacs_template_files(tpl, staging)
            _generate_dicomdir_dcmtk(staging)

            safe_name = "".join(
                c for c in _ascii_safe_text(patient_name) if c.isalnum() or c in " _-"
            )[:32]
            safe_patient_id = "".join(
                c for c in _ascii_safe_text(patient_id) if c.isalnum() or c in "_-"
            )[:32] or "UNKNOWNID"
            iso_filename = f"KPACS_{safe_name}_{safe_patient_id}.iso"
            iso_path = os.path.join(self.temp_dir, iso_filename)

            # No Rock Ridge: K-PACS is Windows-only; macOS Finder often shows RR-heavy ISOs as empty.
            _create_iso(staging, iso_path, patient_name, rock_ridge=None)
            return iso_path
        finally:
            if os.path.isdir(staging):
                try:
                    shutil.rmtree(staging)
                except OSError as e:
                    logger.warning("Could not remove K-PACS staging %s: %s", staging, e)


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

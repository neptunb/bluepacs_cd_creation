import asyncio
import os
import logging
import io
import zipfile
from pathlib import Path
from typing import Callable, Optional

import aiohttp
from pynetdicom import AE, evt, StoragePresentationContexts, build_role
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelGet,
    PatientRootQueryRetrieveInformationModelMove,
    StudyRootQueryRetrieveInformationModelGet,
    StudyRootQueryRetrieveInformationModelMove,
)
from pydicom.dataset import Dataset
from pydicom.uid import (
    UID,
    ExplicitVRLittleEndian,
    ImplicitVRLittleEndian,
    DeflatedExplicitVRLittleEndian,
    ExplicitVRBigEndian,
)

logger = logging.getLogger(__name__)


class DicomRetrieveService:
    """Retrieves DICOM files from a remote DICOM node via C-GET or C-MOVE."""

    def __init__(
        self,
        local_ae: str,
        local_port: int,
        remote_ae: str,
        remote_host: str,
        remote_port: int,
        orthanc_url: str = "",
        orthanc_user: str = "",
        orthanc_password: str = "",
    ):
        self.local_ae = local_ae
        self.local_port = local_port
        self.remote_ae = remote_ae
        self.remote_host = remote_host
        self.remote_port = remote_port
        self.orthanc_url = orthanc_url.rstrip("/")
        self.orthanc_auth = (
            aiohttp.BasicAuth(orthanc_user, orthanc_password)
            if orthanc_user
            else None
        )

    async def retrieve_study(
        self,
        study_instance_uid: str,
        output_dir: str,
        series_filter: Optional[list[str]] = None,
        on_instance_retrieved: Optional[Callable[[int, int], None]] = None,
    ) -> int:
        if self.orthanc_url:
            return await self._retrieve_study_via_orthanc(
                study_instance_uid=study_instance_uid,
                output_dir=output_dir,
                series_filter=series_filter,
                on_instance_retrieved=on_instance_retrieved,
            )

        def _retrieve():
            os.makedirs(output_dir, exist_ok=True)
            file_count = 0
            byte_count = 0

            def handle_store(event):
                nonlocal file_count, byte_count
                ds = event.dataset
                ds.file_meta = event.file_meta

                series_uid = str(getattr(ds, "SeriesInstanceUID", "unknown"))
                sop_uid = str(getattr(ds, "SOPInstanceUID", f"file_{file_count}"))

                if series_filter and series_uid not in series_filter:
                    return 0x0000

                series_dir = os.path.join(output_dir, series_uid)
                os.makedirs(series_dir, exist_ok=True)

                filepath = os.path.join(series_dir, f"{sop_uid}.dcm")
                ds.save_as(filepath, write_like_original=False)
                file_count += 1
                try:
                    byte_count += os.path.getsize(filepath)
                except OSError:
                    pass
                if on_instance_retrieved:
                    on_instance_retrieved(file_count, byte_count)
                return 0x0000

            handlers = [(evt.EVT_C_STORE, handle_store)]
            move_scp = None

            ae = AE(ae_title=self.local_ae)
            # Large studies (hundreds of instances) exceed pynetdicom defaults (~30s).
            ae.acse_timeout = 120
            ae.network_timeout = 120
            ae.dimse_timeout = 3600

            qr_contexts = [
                StudyRootQueryRetrieveInformationModelGet,
                StudyRootQueryRetrieveInformationModelMove,
                PatientRootQueryRetrieveInformationModelGet,
                PatientRootQueryRetrieveInformationModelMove,
            ]
            for qr in qr_contexts:
                ae.add_requested_context(qr)

            # C-GET sub-operations: remote sends C-STORE on the SAME association,
            # so storage SOP classes must be *requested* (not just supported).
            # DICOM allows max 128 presentation contexts per association.
            max_storage = 128 - len(qr_contexts)
            requested_storage_uids: set[str] = set()

            # Prioritize SOP classes seen failing in remote PACS logs so they
            # are always included even if StoragePresentationContexts is truncated.
            prioritized_storage_uids = [
                UID("1.2.840.10008.5.1.4.1.1.2"),   # CT Image Storage
                UID("1.2.840.10008.5.1.4.1.1.7"),   # Secondary Capture Image Storage
                UID("1.2.840.10008.5.1.4.1.1.11.1"),  # Grayscale Softcopy Presentation State
                UID("1.2.840.10008.5.1.4.1.1.20"),  # Nuclear Medicine Image Storage
                UID("1.2.840.10008.5.1.4.1.1.88.67"),  # X-Ray Radiation Dose SR Storage
            ]
            preferred_transfer_syntaxes = [
                ExplicitVRLittleEndian,
                ImplicitVRLittleEndian,
                DeflatedExplicitVRLittleEndian,
                ExplicitVRBigEndian,
            ]

            for sop_uid in prioritized_storage_uids:
                if len(requested_storage_uids) >= max_storage:
                    break
                ae.add_requested_context(
                    sop_uid,
                    preferred_transfer_syntaxes,
                )
                requested_storage_uids.add(str(sop_uid))

            for cx in StoragePresentationContexts:
                sop_uid = str(cx.abstract_syntax)
                if sop_uid in requested_storage_uids:
                    continue
                if len(requested_storage_uids) >= max_storage:
                    break
                ae.add_requested_context(cx.abstract_syntax)
                requested_storage_uids.add(sop_uid)

            # For C-GET, peer sends C-STORE over the same association.
            # Negotiate SCP role for storage SOP classes we requested.
            storage_role_ext_neg = [
                build_role(UID(sop_uid), scu_role=True, scp_role=True)
                for sop_uid in requested_storage_uids
            ]

            # Also register as supported for C-MOVE SCP fallback later.
            for cx in StoragePresentationContexts:
                ae.add_supported_context(cx.abstract_syntax, cx.transfer_syntax)

            ds = Dataset()
            ds.QueryRetrieveLevel = "STUDY"
            ds.StudyInstanceUID = study_instance_uid

            assoc = ae.associate(
                self.remote_host,
                self.remote_port,
                ae_title=self.remote_ae,
                evt_handlers=handlers,
                ext_neg=storage_role_ext_neg,
            )
            if assoc.is_established:
                if assoc.accepted_contexts:
                    get_models = [
                        StudyRootQueryRetrieveInformationModelGet,
                        PatientRootQueryRetrieveInformationModelGet,
                    ]
                    for get_model in get_models:
                        try:
                            responses = assoc.send_c_get(ds, get_model)
                            for status, identifier in responses:
                                if not status:
                                    logger.error("Connection timed out or was aborted")
                                    break
                            if file_count > 0:
                                break
                        except Exception as e:
                            logger.info("C-GET with %s not available: %s", get_model.name, e)
                assoc.release()

            # C-GET not supported by remote (common with some PACS/OsiriX) -> try C-MOVE.
            if file_count == 0:
                try:
                    move_scp = ae.start_server(
                        ("0.0.0.0", self.local_port),
                        block=False,
                        evt_handlers=handlers,
                    )
                    move_models = [
                        StudyRootQueryRetrieveInformationModelMove,
                        PatientRootQueryRetrieveInformationModelMove,
                    ]
                    for move_model in move_models:
                        if file_count > 0:
                            break
                        move_assoc = None
                        try:
                            move_assoc = ae.associate(
                                self.remote_host,
                                self.remote_port,
                                ae_title=self.remote_ae,
                            )
                            if not move_assoc.is_established or not move_assoc.accepted_contexts:
                                logger.error(
                                    "C-MOVE association rejected "
                                    "(model=%s)",
                                    getattr(move_model, "name", move_model),
                                )
                                continue
                            move_responses = move_assoc.send_c_move(
                                ds,
                                self.local_ae,
                                move_model,
                            )
                            for status, identifier in move_responses:
                                if not status:
                                    logger.error("C-MOVE timed out or was aborted")
                                    break
                        except Exception as e:
                            logger.info(
                                "C-MOVE with %s not available: %s",
                                getattr(move_model, "name", move_model),
                                e,
                            )
                        finally:
                            if move_assoc is not None and move_assoc.is_established:
                                move_assoc.release()
                except Exception as e:
                    logger.error("C-MOVE fallback failed: %s", e)
                finally:
                    if move_scp is not None:
                        move_scp.shutdown()

            if file_count == 0:
                logger.error(
                    "Association rejected, aborted, or never connected: %s",
                    assoc.rejection_reason if hasattr(assoc, "rejection_reason") else "unknown",
                )

            return file_count

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _retrieve)

    async def _retrieve_study_via_orthanc(
        self,
        study_instance_uid: str,
        output_dir: str,
        series_filter: Optional[list[str]] = None,
        on_instance_retrieved: Optional[Callable[[int, int], None]] = None,
    ) -> int:
        os.makedirs(output_dir, exist_ok=True)
        timeout = aiohttp.ClientTimeout(total=120)
        file_count = 0
        byte_count = 0
        diagnostics: dict[str, int] = {
            "series_total": 0,
            "series_after_filter": 0,
            "instances_listed": 0,
            "instances_downloaded": 0,
        }
        http_errors: list[str] = []

        async with aiohttp.ClientSession(auth=self.orthanc_auth, timeout=timeout) as session:
            # 1) If caller already sent an Orthanc study resource ID, this resolves directly.
            study_id = ""
            direct_url = f"{self.orthanc_url}/studies/{study_instance_uid}"
            async with session.get(direct_url) as direct_resp:
                if direct_resp.status == 200:
                    study_id = study_instance_uid

            # 2) Try UID -> resource via /tools/lookup (text/plain body).
            if not study_id:
                lookup_url = f"{self.orthanc_url}/tools/lookup"
                async with session.post(
                    lookup_url,
                    data=study_instance_uid,
                    headers={"Content-Type": "text/plain"},
                ) as resp:
                    if resp.status == 200:
                        lookup_rows = await resp.json()
                        if isinstance(lookup_rows, list):
                            for row in lookup_rows:
                                if row.get("Type") == "Study" and row.get("ID"):
                                    study_id = row["ID"]
                                    break

            # 3) Last fallback: scan study IDs and match MainDicomTags.StudyInstanceUID.
            if not study_id:
                studies_url = f"{self.orthanc_url}/studies"
                async with session.get(studies_url) as ids_resp:
                    if ids_resp.status == 200:
                        ids = await ids_resp.json()
                        if isinstance(ids, list):
                            for sid in ids:
                                meta_url = f"{self.orthanc_url}/studies/{sid}"
                                async with session.get(meta_url) as meta_resp:
                                    if meta_resp.status != 200:
                                        continue
                                    meta = await meta_resp.json()
                                uid = (
                                    (meta.get("MainDicomTags", {}) or {}).get("StudyInstanceUID", "")
                                )
                                if uid == study_instance_uid:
                                    study_id = sid
                                    break
                    else:
                        http_errors.append(f"GET /studies -> {ids_resp.status}")

            if not study_id:
                logger.warning("Orthanc retrieve: study not resolved for %s", study_instance_uid)
                errs = "; ".join(http_errors) if http_errors else "none"
                raise RuntimeError(
                    "Orthanc retrieve study resolution failed. "
                    f"study_uid={study_instance_uid} http_errors={errs}"
                )

            study_url = f"{self.orthanc_url}/studies/{study_id}"
            async with session.get(study_url) as study_resp:
                if study_resp.status != 200:
                    body = (await study_resp.text())[:500]
                    raise RuntimeError(
                        f"Orthanc study metadata failed HTTP {study_resp.status}: {body}"
                    )
                study_meta = await study_resp.json()

            series_ids = study_meta.get("Series", []) or []
            if not isinstance(series_ids, list) or not series_ids:
                logger.warning(
                    "Orthanc retrieve: no series IDs in study %s",
                    study_instance_uid,
                )
                raise RuntimeError(
                    "Orthanc retrieve study has no series. "
                    f"study_uid={study_instance_uid} study_id={study_id}"
                )
            diagnostics["series_total"] = len(series_ids)

            for sid in series_ids:
                if not sid:
                    continue

                series_url = f"{self.orthanc_url}/series/{sid}"
                async with session.get(series_url) as series_resp:
                    if series_resp.status != 200:
                        if len(http_errors) < 10:
                            http_errors.append(f"GET /series/{sid} -> {series_resp.status}")
                        continue
                    series_meta = await series_resp.json()

                series_main = series_meta.get("MainDicomTags", {}) or {}
                series_uid = str(series_main.get("SeriesInstanceUID", sid))
                if (
                    series_filter
                    and series_uid not in series_filter
                    and sid not in series_filter
                ):
                    continue
                diagnostics["series_after_filter"] += 1

                series_dir = os.path.join(output_dir, series_uid)
                os.makedirs(series_dir, exist_ok=True)

                instance_ids = series_meta.get("Instances", []) or []
                if not isinstance(instance_ids, list):
                    continue
                diagnostics["instances_listed"] += len(instance_ids)

                for iid in instance_ids:
                    file_url = f"{self.orthanc_url}/instances/{iid}/file"
                    async with session.get(file_url) as file_resp:
                        if file_resp.status != 200:
                            if len(http_errors) < 10:
                                http_errors.append(
                                    f"GET /instances/{iid}/file -> {file_resp.status}"
                                )
                            continue
                        data = await file_resp.read()
                    if not data:
                        continue
                    filepath = os.path.join(series_dir, f"{iid}.dcm")
                    with open(filepath, "wb") as f:
                        f.write(data)
                    file_count += 1
                    byte_count += len(data)
                    diagnostics["instances_downloaded"] += 1
                    if on_instance_retrieved:
                        on_instance_retrieved(file_count, byte_count)

            if file_count == 0:
                # Final fallback: download whole study archive from Orthanc and extract.
                archive_url = f"{self.orthanc_url}/studies/{study_id}/archive"
                async with session.get(archive_url) as archive_resp:
                    if archive_resp.status == 200:
                        archive_bytes = await archive_resp.read()
                        if archive_bytes:
                            try:
                                with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
                                    zf.extractall(output_dir)
                                for root, _dirs, files in os.walk(output_dir):
                                    for fn in files:
                                        fp = os.path.join(root, fn)
                                        try:
                                            size = os.path.getsize(fp)
                                        except OSError:
                                            continue
                                        if size > 0:
                                            file_count += 1
                                            byte_count += size
                                            diagnostics["instances_downloaded"] += 1
                                            if on_instance_retrieved:
                                                on_instance_retrieved(
                                                    file_count, byte_count
                                                )
                            except Exception as e:
                                logger.warning(
                                    "Orthanc retrieve: archive extract failed for %s: %s",
                                    study_instance_uid,
                                    e,
                                )
                    else:
                        if len(http_errors) < 10:
                            http_errors.append(
                                f"GET /studies/{study_id}/archive -> {archive_resp.status}"
                            )

        if file_count == 0:
            errs = "; ".join(http_errors) if http_errors else "none"
            raise RuntimeError(
                "Orthanc retrieve returned zero files. "
                f"study_uid={study_instance_uid} study_id={study_id} "
                f"series_total={diagnostics['series_total']} "
                f"series_after_filter={diagnostics['series_after_filter']} "
                f"instances_listed={diagnostics['instances_listed']} "
                f"instances_downloaded={diagnostics['instances_downloaded']} "
                f"http_errors={errs}"
            )

        logger.info(
            "Orthanc retrieve: downloaded %d instances for study %s",
            file_count,
            study_instance_uid,
        )
        return file_count

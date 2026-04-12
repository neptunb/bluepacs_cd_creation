import asyncio
import logging
from datetime import date, timedelta
from typing import Optional

from pynetdicom import AE, evt
from pynetdicom.sop_class import (
    PatientRootQueryRetrieveInformationModelFind,
    StudyRootQueryRetrieveInformationModelFind,
    Verification,
)
from pydicom.dataset import Dataset

from services.search_normalize import patient_name_for_find, plain_query_value

logger = logging.getLogger(__name__)

# Orthanc (and many SCP) handle StudyRoot better than PatientRoot
FIND_MODELS = [
    StudyRootQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelFind,
]


def _extract_str(identifier, attr: str, default: str = "") -> str:
    val = getattr(identifier, attr, None)
    if val is None:
        return default
    return str(val)


class DicomQueryService:
    def __init__(
        self,
        local_ae: str,
        remote_ae: str,
        remote_host: str,
        remote_port: int,
    ):
        self.local_ae = local_ae
        self.remote_ae = remote_ae
        self.remote_host = remote_host
        self.remote_port = remote_port

    def _make_ae(self) -> AE:
        ae = AE(ae_title=self.local_ae)
        ae.add_requested_context(Verification)
        for model in FIND_MODELS:
            ae.add_requested_context(model)
        return ae

    def _associate(self, ae: AE):
        assoc = ae.associate(
            self.remote_host, self.remote_port, ae_title=self.remote_ae
        )
        if not assoc.is_established:
            reason = "unknown"
            if hasattr(assoc, "result") and assoc.result is not None:
                reason = f"result=0x{assoc.result:04X}"
            logger.error(
                "Association REJECTED by %s@%s:%d — %s",
                self.remote_ae, self.remote_host, self.remote_port, reason,
            )
            return None
        logger.info(
            "Association ESTABLISHED with %s@%s:%d",
            self.remote_ae, self.remote_host, self.remote_port,
        )
        return assoc

    def _cfind(self, assoc, dataset: Dataset) -> list:
        """Try C-FIND with StudyRoot first, fall back to PatientRoot."""
        results = []
        for model in FIND_MODELS:
            try:
                responses = assoc.send_c_find(dataset, model)
                for status, identifier in responses:
                    if status is None:
                        logger.warning("C-FIND: connection lost (status=None)")
                        break
                    code = status.Status
                    if code in (0xFF00, 0xFF01) and identifier:
                        results.append(identifier)
                    elif code == 0x0000:
                        break  # success, no more results
                    elif code == 0xA700:
                        logger.error("C-FIND refused: out of resources (0xA700)")
                    elif code == 0xA900:
                        logger.error("C-FIND: identifier does not match SOP class (0xA900)")
                    elif code == 0xC000:
                        logger.error("C-FIND: unable to process (0xC000)")
                    else:
                        logger.debug("C-FIND status: 0x%04X", code)
            except Exception as e:
                logger.warning("C-FIND with %s failed: %s — trying next model", model.keyword, e)
                continue

            if results:
                logger.info("C-FIND returned %d results via %s", len(results), model.keyword)
                return results

        logger.info("C-FIND returned 0 results (tried %d query models)", len(FIND_MODELS))
        return results

    async def verify(self) -> bool:
        def _verify():
            ae = self._make_ae()
            assoc = self._associate(ae)
            if not assoc:
                return False
            try:
                status = assoc.send_c_echo()
                return status is not None and status.Status == 0x0000
            finally:
                assoc.release()

        return await asyncio.get_event_loop().run_in_executor(None, _verify)

    async def find_patients(
        self,
        patient_name: str = "",
        patient_id: str = "",
    ) -> list[dict]:
        """Search patients via STUDY-level C-FIND (most compatible with Orthanc)."""
        def _find():
            ae = self._make_ae()
            assoc = self._associate(ae)
            if not assoc:
                return []

            try:
                name_q = patient_name_for_find(patient_name)
                id_q = plain_query_value(patient_id)

                ds = Dataset()
                ds.QueryRetrieveLevel = "STUDY"
                ds.PatientName = name_q if name_q else "*"
                ds.PatientID = id_q if id_q else "*"
                ds.PatientBirthDate = ""
                ds.PatientSex = ""
                ds.StudyInstanceUID = ""
                ds.StudyDate = ""
                ds.StudyDescription = ""
                ds.ModalitiesInStudy = ""
                ds.NumberOfStudyRelatedSeries = ""

                logger.info(
                    "C-FIND patient search: PatientName=%r  PatientID=%r  to %s@%s:%d",
                    ds.PatientName, ds.PatientID,
                    self.remote_ae, self.remote_host, self.remote_port,
                )

                identifiers = self._cfind(assoc, ds)

                merged: dict[str, dict] = {}
                for ident in identifiers:
                    pid = _extract_str(ident, "PatientID")
                    if not pid:
                        continue
                    if pid not in merged:
                        merged[pid] = {
                            "patient_id": pid,
                            "patient_name": _extract_str(ident, "PatientName"),
                            "birth_date": _extract_str(ident, "PatientBirthDate"),
                            "sex": _extract_str(ident, "PatientSex"),
                        }

                logger.info("Patient search returned %d unique patients", len(merged))
                return list(merged.values())

            finally:
                assoc.release()

        return await asyncio.get_event_loop().run_in_executor(None, _find)

    async def find_studies(
        self,
        patient_id: str,
        modality: Optional[str] = None,
        study_date_from: Optional[str] = None,
        study_date_to: Optional[str] = None,
    ) -> list[dict]:
        def _find():
            ae = self._make_ae()
            assoc = self._associate(ae)
            if not assoc:
                return []

            try:
                ds = Dataset()
                ds.QueryRetrieveLevel = "STUDY"
                ds.PatientID = patient_id
                ds.PatientName = ""
                ds.StudyInstanceUID = ""
                ds.StudyDate = ""
                ds.StudyTime = ""
                ds.StudyDescription = ""
                ds.AccessionNumber = ""
                ds.ModalitiesInStudy = modality or ""
                ds.NumberOfStudyRelatedSeries = ""
                ds.NumberOfStudyRelatedInstances = ""

                if study_date_from and study_date_to:
                    ds.StudyDate = f"{study_date_from}-{study_date_to}"
                elif study_date_from:
                    ds.StudyDate = f"{study_date_from}-"
                elif study_date_to:
                    ds.StudyDate = f"-{study_date_to}"

                identifiers = self._cfind(assoc, ds)

                results = []
                for ident in identifiers:
                    results.append({
                        "study_instance_uid": _extract_str(ident, "StudyInstanceUID"),
                        "study_date": _extract_str(ident, "StudyDate"),
                        "study_time": _extract_str(ident, "StudyTime"),
                        "study_description": _extract_str(ident, "StudyDescription"),
                        "accession_number": _extract_str(ident, "AccessionNumber"),
                        "modalities_in_study": _extract_str(ident, "ModalitiesInStudy"),
                        "number_of_series": int(getattr(ident, "NumberOfStudyRelatedSeries", 0) or 0),
                        "number_of_instances": int(getattr(ident, "NumberOfStudyRelatedInstances", 0) or 0),
                        "patient_id": _extract_str(ident, "PatientID"),
                        "patient_name": _extract_str(ident, "PatientName"),
                    })

                return results

            finally:
                assoc.release()

        return await asyncio.get_event_loop().run_in_executor(None, _find)

    async def find_recent_studies(self, limit: int = 10) -> list[dict]:
        """C-FIND at STUDY level; sort by StudyDate/Time; return newest `limit` rows."""
        limit = max(1, min(limit, 100))

        def _sort_key(row: dict) -> tuple:
            d = (row["study_date"] or "00000000").replace("-", "")[:8]
            t = (row["study_time"] or "000000").replace(":", "")[:6]
            return (d, t)

        def _find():
            ae = self._make_ae()
            assoc = self._associate(ae)
            if not assoc:
                return []

            try:
                end_d = date.today()
                start_d = end_d - timedelta(days=365 * 10)
                study_date_range = f"{start_d.strftime('%Y%m%d')}-{end_d.strftime('%Y%m%d')}"

                ds = Dataset()
                ds.QueryRetrieveLevel = "STUDY"
                ds.PatientID = "*"
                ds.PatientName = ""
                ds.StudyInstanceUID = ""
                ds.StudyDate = study_date_range
                ds.StudyTime = ""
                ds.StudyDescription = ""
                ds.AccessionNumber = ""
                ds.ModalitiesInStudy = ""
                ds.NumberOfStudyRelatedSeries = ""
                ds.NumberOfStudyRelatedInstances = ""

                logger.info(
                    "C-FIND recent studies (limit=%s) → %s@%s:%d",
                    limit, self.remote_ae, self.remote_host, self.remote_port,
                )

                identifiers = self._cfind(assoc, ds)
                rows = []
                for ident in identifiers:
                    rows.append({
                        "study_instance_uid": _extract_str(ident, "StudyInstanceUID"),
                        "study_date": _extract_str(ident, "StudyDate"),
                        "study_time": _extract_str(ident, "StudyTime"),
                        "study_description": _extract_str(ident, "StudyDescription"),
                        "accession_number": _extract_str(ident, "AccessionNumber"),
                        "modalities_in_study": _extract_str(ident, "ModalitiesInStudy"),
                        "number_of_series": int(getattr(ident, "NumberOfStudyRelatedSeries", 0) or 0),
                        "number_of_instances": int(getattr(ident, "NumberOfStudyRelatedInstances", 0) or 0),
                        "patient_id": _extract_str(ident, "PatientID"),
                        "patient_name": _extract_str(ident, "PatientName"),
                    })

                rows.sort(key=_sort_key, reverse=True)
                return rows[:limit]

            finally:
                assoc.release()

        return await asyncio.get_event_loop().run_in_executor(None, _find)

    async def find_series(self, study_instance_uid: str) -> list[dict]:
        def _find():
            ae = self._make_ae()
            assoc = self._associate(ae)
            if not assoc:
                return []

            try:
                ds = Dataset()
                ds.QueryRetrieveLevel = "SERIES"
                ds.StudyInstanceUID = study_instance_uid
                ds.SeriesInstanceUID = ""
                ds.SeriesNumber = ""
                ds.SeriesDescription = ""
                ds.Modality = ""
                ds.NumberOfSeriesRelatedInstances = ""
                ds.BodyPartExamined = ""

                identifiers = self._cfind(assoc, ds)

                results = []
                for ident in identifiers:
                    results.append({
                        "series_instance_uid": _extract_str(ident, "SeriesInstanceUID"),
                        "series_number": int(getattr(ident, "SeriesNumber", 0) or 0),
                        "series_description": _extract_str(ident, "SeriesDescription"),
                        "modality": _extract_str(ident, "Modality"),
                        "number_of_instances": int(getattr(ident, "NumberOfSeriesRelatedInstances", 0) or 0),
                        "body_part_examined": _extract_str(ident, "BodyPartExamined"),
                    })

                return results

            finally:
                assoc.release()

        return await asyncio.get_event_loop().run_in_executor(None, _find)

    async def diagnostic_cfind(self, patient_name: str = "", patient_id: str = "") -> dict:
        """Run a raw C-FIND and return detailed debug info."""
        def _diag():
            ae = self._make_ae()
            info = {
                "local_ae": self.local_ae,
                "remote_ae": self.remote_ae,
                "remote_host": self.remote_host,
                "remote_port": self.remote_port,
                "association": "failed",
                "models_tried": [],
                "results_per_model": {},
                "raw_statuses": [],
                "patients_found": [],
            }

            assoc = self._associate(ae)
            if not assoc:
                return info

            info["association"] = "established"

            try:
                name_q = patient_name_for_find(patient_name)
                id_q = plain_query_value(patient_id)

                ds = Dataset()
                ds.QueryRetrieveLevel = "STUDY"
                ds.PatientName = name_q if name_q else "*"
                ds.PatientID = id_q if id_q else "*"
                ds.PatientBirthDate = ""
                ds.PatientSex = ""
                ds.StudyInstanceUID = ""

                info["query"] = {
                    "QueryRetrieveLevel": ds.QueryRetrieveLevel,
                    "PatientName": str(ds.PatientName),
                    "PatientID": str(ds.PatientID),
                }

                for model in FIND_MODELS:
                    model_name = model.keyword
                    info["models_tried"].append(model_name)
                    count = 0
                    try:
                        responses = assoc.send_c_find(ds, model)
                        for status, identifier in responses:
                            if status is None:
                                info["raw_statuses"].append(f"{model_name}: None (lost)")
                                break
                            code = status.Status
                            info["raw_statuses"].append(f"{model_name}: 0x{code:04X}")
                            if code in (0xFF00, 0xFF01) and identifier:
                                count += 1
                                pid = _extract_str(identifier, "PatientID")
                                pname = _extract_str(identifier, "PatientName")
                                if count <= 10:
                                    info["patients_found"].append({
                                        "patient_id": pid,
                                        "patient_name": pname,
                                    })
                    except Exception as e:
                        info["raw_statuses"].append(f"{model_name}: ERROR {e}")

                    info["results_per_model"][model_name] = count

                    if count > 0:
                        break

            finally:
                assoc.release()

            return info

        return await asyncio.get_event_loop().run_in_executor(None, _diag)

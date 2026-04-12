import asyncio
import json
import logging
from datetime import date, timedelta
from typing import Any, Optional

import aiohttp

from config import config
from services.search_normalize import (
    normalize_modalities_in_study,
    patient_name_for_find,
    plain_query_value,
)

logger = logging.getLogger(__name__)

_BODY_PREVIEW_LIMIT = 8000


def _format_json_for_log(obj: Any) -> str:
    try:
        s = json.dumps(obj, indent=2 if config.DEBUG else None, default=str)
    except (TypeError, ValueError):
        s = str(obj)
    if len(s) > _BODY_PREVIEW_LIMIT:
        return s[:_BODY_PREVIEW_LIMIT] + "\n... [truncated]"
    return s


def _log_orthanc_request(
    method: str,
    url: str,
    *,
    params: dict | None = None,
    json_body: dict | None = None,
    label: str | None = None,
) -> None:
    lines = [
        f"[Orthanc REST] {label + ' — ' if label else ''}{method} {url}",
    ]
    if params:
        lines.append(f"  query_params: {_format_json_for_log(params)}")
    if json_body is not None:
        lines.append(f"  json_body:\n{_format_json_for_log(json_body)}")
    logger.info("\n".join(lines))


class OrthancApiService:
    """Query Orthanc via its REST API — bypasses DicomCheckModalityHost restrictions."""

    def __init__(self, orthanc_url: str, username: str = "", password: str = ""):
        self.base_url = orthanc_url.rstrip("/")
        self.auth = aiohttp.BasicAuth(username, password) if username else None

    async def _get(
        self,
        path: str,
        params: dict | None = None,
        *,
        label: str | None = None,
    ) -> list | dict | None:
        url = f"{self.base_url}{path}"
        _log_orthanc_request("GET", url, params=params, label=label)
        try:
            async with aiohttp.ClientSession(auth=self.auth) as session:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    logger.info(
                        "[Orthanc REST] GET %s -> HTTP %s", url, resp.status
                    )
                    if resp.status == 200:
                        return await resp.json()
                    body = (await resp.text())[:800]
                    logger.warning(
                        "Orthanc API GET %s returned %d body_preview=%r",
                        url,
                        resp.status,
                        body,
                    )
                    return None
        except Exception as e:
            logger.error("Orthanc API request failed: %s — %s", url, e)
            return None

    async def _post(
        self,
        path: str,
        data: dict,
        timeout_sec: int = 60,
        *,
        label: str | None = None,
    ) -> list | dict | None:
        url = f"{self.base_url}{path}"
        _log_orthanc_request("POST", url, json_body=data, label=label)
        try:
            async with aiohttp.ClientSession(auth=self.auth) as session:
                async with session.post(
                    url,
                    json=data,
                    timeout=aiohttp.ClientTimeout(total=timeout_sec),
                ) as resp:
                    logger.info(
                        "[Orthanc REST] POST %s -> HTTP %s", url, resp.status
                    )
                    if resp.status == 200:
                        payload = await resp.json()
                        if isinstance(payload, list):
                            logger.info(
                                "[Orthanc REST] POST %s -> JSON array length=%d",
                                url,
                                len(payload),
                            )
                        elif isinstance(payload, dict):
                            logger.info(
                                "[Orthanc REST] POST %s -> JSON object keys=%s",
                                url,
                                list(payload.keys())[:20],
                            )
                        return payload
                    body = (await resp.text())[:800]
                    logger.warning(
                        "Orthanc API POST %s returned %d body_preview=%r",
                        url,
                        resp.status,
                        body,
                    )
                    return None
        except Exception as e:
            logger.error("Orthanc API POST failed: %s — %s", url, e)
            return None

    async def find_patients(
        self,
        patient_name: str = "",
        patient_id: str = "",
        study_date_from: Optional[str] = None,
        study_date_to: Optional[str] = None,
    ) -> list[dict]:
        name_plain = patient_name_for_find(patient_name)
        id_plain = plain_query_value(patient_id)
        date_from = (study_date_from or "").strip()
        date_to = (study_date_to or "").strip()
        has_study_dates = bool(date_from or date_to)

        if has_study_dates:
            query: dict[str, str] = {}
            if date_from and date_to:
                query["StudyDate"] = f"{date_from}-{date_to}"
            elif date_from:
                query["StudyDate"] = f"{date_from}-"
            elif date_to:
                query["StudyDate"] = f"-{date_to}"
            query["PatientName"] = name_plain if name_plain else "*"
            query["PatientID"] = id_plain if id_plain else "*"
            payload = {
                "Level": "Study",
                "Query": query,
                "Expand": True,
            }
            results = await self._post(
                "/tools/find",
                payload,
                timeout_sec=120,
                label="find_patients(study_date)",
            )
            if results is None:
                return []

            merged: dict[str, dict] = {}
            for item in results:
                pm = item.get("PatientMainDicomTags") or {}
                pid = pm.get("PatientID") or ""
                if not pid:
                    continue
                if pid not in merged:
                    merged[pid] = {
                        "patient_id": pid,
                        "patient_name": pm.get("PatientName", ""),
                        "birth_date": pm.get("PatientBirthDate", ""),
                        "sex": pm.get("PatientSex", ""),
                    }
            patients = list(merged.values())
            logger.info(
                "Orthanc REST found %d patients (study-date query, %d studies)",
                len(patients),
                len(results),
            )
            return patients

        query = {}
        if name_plain:
            query["PatientName"] = name_plain
        if id_plain:
            query["PatientID"] = id_plain

        if not query:
            query["PatientName"] = "*"

        payload = {
            "Level": "Patient",
            "Query": query,
            "Expand": True,
        }

        results = await self._post("/tools/find", payload, label="find_patients")

        if results is None:
            return []

        patients = []
        for item in results:
            main = item.get("MainDicomTags", {})
            patients.append({
                "patient_id": main.get("PatientID", ""),
                "patient_name": main.get("PatientName", ""),
                "birth_date": main.get("PatientBirthDate", ""),
                "sex": main.get("PatientSex", ""),
            })

        logger.info("Orthanc REST found %d patients", len(patients))
        return patients

    async def find_studies(
        self,
        patient_id: str,
        modality: Optional[str] = None,
        study_date_from: Optional[str] = None,
        study_date_to: Optional[str] = None,
    ) -> list[dict]:
        query: dict = {"PatientID": patient_id}

        if modality:
            query["ModalitiesInStudy"] = modality

        if study_date_from and study_date_to:
            query["StudyDate"] = f"{study_date_from}-{study_date_to}"
        elif study_date_from:
            query["StudyDate"] = f"{study_date_from}-"
        elif study_date_to:
            query["StudyDate"] = f"-{study_date_to}"

        payload = {
            "Level": "Study",
            "Query": query,
            "Expand": True,
        }

        results = await self._post("/tools/find", payload, label="find_studies")
        if results is None:
            return []

        studies = []
        for item in results:
            main = item.get("MainDicomTags", {})
            patient_main = item.get("PatientMainDicomTags", {})
            studies.append({
                "study_instance_uid": main.get("StudyInstanceUID", ""),
                "study_date": main.get("StudyDate", ""),
                "study_time": main.get("StudyTime", ""),
                "study_description": main.get("StudyDescription", ""),
                "accession_number": main.get("AccessionNumber", ""),
                "modalities_in_study": normalize_modalities_in_study(
                    main.get("ModalitiesInStudy", "")
                ),
                "number_of_series": len(item.get("Series", [])),
                "number_of_instances": 0,
                "patient_id": patient_main.get("PatientID", ""),
                "patient_name": patient_main.get("PatientName", ""),
            })

        return studies

    def _study_sort_key(self, item: dict) -> tuple:
        main = item.get("MainDicomTags", {})
        d = (main.get("StudyDate") or "00000000").replace("-", "")[:8]
        t = (main.get("StudyTime") or "000000").replace(":", "")[:6]
        return (d, t)

    @staticmethod
    def _study_date_cmp_value(item: dict) -> str:
        main = item.get("MainDicomTags", {})
        return (main.get("StudyDate") or "").replace("-", "")[:8]

    def _study_matches_date_window(
        self,
        item: dict,
        study_date_from: Optional[str],
        study_date_to: Optional[str],
    ) -> bool:
        d_from = (study_date_from or "").strip()
        d_to = (study_date_to or "").strip()
        if not d_from and not d_to:
            return True
        raw = self._study_date_cmp_value(item)
        if len(raw) < 8:
            return False
        if d_from and raw < d_from:
            return False
        if d_to and raw > d_to:
            return False
        return True

    def _study_row_from_item(self, item: dict) -> dict:
        main = item.get("MainDicomTags", {})
        patient_main = item.get("PatientMainDicomTags", {})
        n_inst = 0
        for ser in item.get("Series", []) or []:
            n_inst += len(ser.get("Instances", []) or [])
        return {
            "study_instance_uid": main.get("StudyInstanceUID", ""),
            "study_date": main.get("StudyDate", ""),
            "study_time": main.get("StudyTime", ""),
            "study_description": main.get("StudyDescription", ""),
            "accession_number": main.get("AccessionNumber", ""),
            "modalities_in_study": normalize_modalities_in_study(
                main.get("ModalitiesInStudy", "")
            ),
            "number_of_series": len(item.get("Series", []) or []),
            "number_of_instances": n_inst,
            "patient_id": patient_main.get("PatientID", ""),
            "patient_name": patient_main.get("PatientName", ""),
        }

    def _study_row_from_study_resource(self, detail: dict) -> dict:
        """Build a study row from ``GET /studies/{id}`` (Series are IDs, not expanded)."""
        main = detail.get("MainDicomTags", {})
        patient_main = detail.get("PatientMainDicomTags", {})
        series = detail.get("Series", []) or []
        n_series = len(series) if isinstance(series, list) else 0
        return {
            "study_instance_uid": main.get("StudyInstanceUID", ""),
            "study_date": main.get("StudyDate", ""),
            "study_time": main.get("StudyTime", ""),
            "study_description": main.get("StudyDescription", ""),
            "accession_number": main.get("AccessionNumber", ""),
            "modalities_in_study": normalize_modalities_in_study(
                main.get("ModalitiesInStudy", "")
            ),
            "number_of_series": n_series,
            "number_of_instances": 0,
            "patient_id": patient_main.get("PatientID", ""),
            "patient_name": patient_main.get("PatientName", ""),
        }

    async def _find_recent_via_study_list(
        self,
        limit: int,
        study_date_from: Optional[str] = None,
        study_date_to: Optional[str] = None,
    ) -> list[dict]:
        """Bypass ``/tools/find`` when Orthanc's indexed search returns no candidates."""
        max_scan = max(1, config.ORTHANC_RECENT_STUDIES_MAX_SCAN)
        conc = max(1, min(128, config.ORTHANC_RECENT_STUDIES_CONCURRENCY))
        list_timeout = aiohttp.ClientTimeout(total=120)
        detail_timeout = aiohttp.ClientTimeout(total=45)
        base = self.base_url
        auth = self.auth
        sem = asyncio.Semaphore(conc)

        async with aiohttp.ClientSession(auth=auth) as session:
            list_url = f"{base}/studies"
            _log_orthanc_request("GET", list_url, label="find_recent_fallback list_study_ids")
            async with session.get(list_url, timeout=list_timeout) as resp:
                logger.info(
                    "[Orthanc REST] GET %s -> HTTP %s", list_url, resp.status
                )
                if resp.status != 200:
                    body = (await resp.text())[:800]
                    logger.warning(
                        "Orthanc fallback list studies failed: %s body_preview=%r",
                        resp.status,
                        body,
                    )
                    return []
                ids = await resp.json()

            if not isinstance(ids, list) or not ids:
                logger.warning("Orthanc fallback: GET /studies returned empty or non-list")
                return []

            total = len(ids)
            if total > max_scan:
                logger.warning(
                    "Orthanc fallback: %d study IDs (capped to last %d for scan); "
                    "raise ORTHANC_RECENT_STUDIES_MAX_SCAN if latest studies are missing",
                    total,
                    max_scan,
                )
                scan_ids = ids[-max_scan:]
            else:
                scan_ids = ids

            async def fetch_detail(sid: str) -> dict | None:
                async with sem:
                    u = f"{base}/studies/{sid}"
                    try:
                        async with session.get(u, timeout=detail_timeout) as r:
                            if r.status != 200:
                                return None
                            return await r.json()
                    except Exception as e:
                        logger.debug(
                            "Orthanc fallback study detail failed %s: %s",
                            sid[:8],
                            e,
                        )
                        return None

            metas = await asyncio.gather(
                *[fetch_detail(sid) for sid in scan_ids],
                return_exceptions=True,
            )

        details: list[dict] = []
        for m in metas:
            if isinstance(m, BaseException):
                continue
            if m and isinstance(m, dict) and m.get("MainDicomTags"):
                details.append(m)

        if not details:
            logger.warning(
                "Orthanc fallback: no study metadata after scanning %d IDs",
                len(scan_ids),
            )
            return []

        details.sort(key=self._study_sort_key, reverse=True)
        if (study_date_from or "").strip() or (study_date_to or "").strip():
            details = [
                d
                for d in details
                if self._study_matches_date_window(d, study_date_from, study_date_to)
            ]
        rows = [self._study_row_from_study_resource(d) for d in details[:limit]]
        logger.info(
            "Orthanc fallback: sorted %d studies with tags, returning %d newest",
            len(details),
            len(rows),
        )
        return rows

    async def find_recent_studies(
        self,
        limit: int = 10,
        study_date_from: Optional[str] = None,
        study_date_to: Optional[str] = None,
    ) -> list[dict]:
        """Return the newest studies (by StudyDate / StudyTime), newest first.

        Note: With MySQL indexing, ``/tools/find`` often yields **0 candidates** (Orthanc fast
        DB filter). We try several queries first; if all are empty, we list study IDs via
        ``GET /studies`` and fetch ``GET /studies/{id}`` to sort by StudyDate (see config
        ``ORTHANC_RECENT_STUDIES_MAX_SCAN``).
        """
        df = (study_date_from or "").strip()
        dt = (study_date_to or "").strip()
        has_date_window = bool(df or dt)
        if has_date_window:
            limit = max(1, min(limit, 2000))
        else:
            limit = max(1, min(limit, 100))

        if df and dt:
            study_date_range = f"{df}-{dt}"
        elif df:
            study_date_range = f"{df}-"
        elif dt:
            study_date_range = f"-{dt}"
        else:
            end_d = date.today()
            start_d = end_d - timedelta(days=365 * 20)
            study_date_range = f"{start_d.strftime('%Y%m%d')}-{end_d.strftime('%Y%m%d')}"

        # Max items to sort when falling back to broad wildcards (avoids huge RAM use).
        max_sort_batch = 8000

        attempts: list[tuple[str, dict]] = [
            (
                "StudyDate_only",
                {
                    "Level": "Study",
                    "Query": {"StudyDate": study_date_range},
                    "Expand": True,
                },
            ),
            (
                "StudyDate_and_PatientName_star",
                {
                    "Level": "Study",
                    "Query": {
                        "StudyDate": study_date_range,
                        "PatientName": "*",
                    },
                    "Expand": True,
                },
            ),
            (
                "PatientName_star_only",
                {
                    "Level": "Study",
                    "Query": {"PatientName": "*"},
                    "Expand": True,
                },
            ),
            (
                "PatientID_star_only",
                {
                    "Level": "Study",
                    "Query": {"PatientID": "*"},
                    "Expand": True,
                },
            ),
        ]

        results: list | None = None
        used_label = ""
        for name, payload in attempts:
            used_label = f"find_recent_studies({name}, limit={limit})"
            results = await self._post(
                "/tools/find",
                payload,
                timeout_sec=120,
                label=used_label,
            )
            if results is None:
                continue
            if len(results) > 0:
                logger.info(
                    "Orthanc recent studies: strategy %r matched %d resources",
                    name,
                    len(results),
                )
                break
            logger.info(
                "Orthanc recent studies: strategy %r returned 0 matches, trying next",
                name,
            )

        if results and len(results) > 0:
            if len(results) > max_sort_batch:
                logger.warning(
                    "Orthanc recent studies: %d matches, sorting first %d only for performance",
                    len(results),
                    max_sort_batch,
                )
                results = results[:max_sort_batch]

            sorted_items = sorted(results, key=self._study_sort_key, reverse=True)
            if has_date_window:
                sorted_items = [
                    it
                    for it in sorted_items
                    if self._study_matches_date_window(it, df, dt)
                ]
            rows = [self._study_row_from_item(item) for item in sorted_items[:limit]]
            logger.info(
                "Orthanc recent studies: returning %d of %d collected (strategy log above)",
                len(rows),
                len(results),
            )
            return rows

        logger.warning(
            "Orthanc recent studies: /tools/find returned no rows; "
            "using GET /studies + per-study metadata fallback"
        )
        return await self._find_recent_via_study_list(
            limit, study_date_from=df or None, study_date_to=dt or None
        )

    async def find_series(self, study_instance_uid: str) -> list[dict]:
        query = {"StudyInstanceUID": study_instance_uid}
        payload = {
            "Level": "Series",
            "Query": query,
            "Expand": True,
        }

        results = await self._post("/tools/find", payload, label="find_series")
        if results is None:
            return []

        series_list = []
        for item in results:
            main = item.get("MainDicomTags", {})
            series_list.append({
                "series_instance_uid": main.get("SeriesInstanceUID", ""),
                "series_number": int(main.get("SeriesNumber", 0) or 0),
                "series_description": main.get("SeriesDescription", ""),
                "modality": main.get("Modality", ""),
                "number_of_instances": len(item.get("Instances", [])),
                "body_part_examined": main.get("BodyPartExamined", ""),
            })

        return series_list

from pydantic import BaseModel, Field, model_validator
from typing import Optional
from datetime import date


class DicomNode(BaseModel):
    ae_title: str
    host: str
    port: int
    name: Optional[str] = None


class PatientQuery(BaseModel):
    node_ae_title: str
    patient_name: Optional[str] = None
    patient_id: Optional[str] = None
    modality: Optional[str] = None
    study_date_from: Optional[str] = None
    study_date_to: Optional[str] = None

    @model_validator(mode="after")
    def require_search_criteria(self):
        has_name_or_id = bool(
            (self.patient_name or "").strip() or (self.patient_id or "").strip()
        )
        has_study_dates = bool(
            (self.study_date_from or "").strip() or (self.study_date_to or "").strip()
        )
        if not has_name_or_id and not has_study_dates:
            raise ValueError(
                "Provide patient name, patient id, and/or study date range (from/to)"
            )
        return self


class PatientResult(BaseModel):
    patient_id: str
    patient_name: str
    birth_date: Optional[str] = None
    sex: Optional[str] = None


class StudyResult(BaseModel):
    study_instance_uid: str
    study_date: Optional[str] = None
    study_time: Optional[str] = None
    study_description: Optional[str] = None
    accession_number: Optional[str] = None
    modalities_in_study: Optional[str] = None
    number_of_series: Optional[int] = None
    number_of_instances: Optional[int] = None
    patient_id: str
    patient_name: str


class SeriesResult(BaseModel):
    series_instance_uid: str
    series_number: Optional[int] = None
    series_description: Optional[str] = None
    modality: str
    number_of_instances: Optional[int] = None
    body_part_examined: Optional[str] = None


class BurnRequest(BaseModel):
    node_ae_title: str
    patient_id: str
    patient_name: str
    studies: list[str]  # list of StudyInstanceUIDs
    series: Optional[list[str]] = None  # optional subset of SeriesInstanceUIDs
    expected_instances: Optional[int] = None
    include_viewer: bool = True
    include_macos_launcher: bool = True
    include_windows_launcher: bool = True
    include_linux_launcher: bool = False
    include_kpacs: bool = True
    # OHIF step 1: retrieve into STUDY/ and offer ZIP only (no ISO; K-PACS unchanged).
    study_zip_only: bool = False

    @model_validator(mode="after")
    def require_platform_when_viewer_on_iso(self):
        if self.study_zip_only or not self.include_viewer:
            return self
        if not (
            self.include_macos_launcher
            or self.include_windows_launcher
            or self.include_linux_launcher
        ):
            raise ValueError(
                "Select at least one viewer platform (macOS, Windows, and/or Linux)."
            )
        return self


class DownloadArtifact(BaseModel):
    """One built file the user can download (name + size on disk)."""

    filename: str
    size: int


class BuildProgress(BaseModel):
    job_id: str
    status: str  # "queued", "retrieving", "building", "complete", "error"
    progress: float  # 0.0 to 1.0
    message: str
    filename: Optional[str] = None
    download_ready: bool = False
    download_kind: str = "ohif_iso"  # ohif_iso | study_zip
    kpacs_filename: Optional[str] = None
    kpacs_download_ready: bool = False
    kpacs_error: Optional[str] = None
    retrieved_instances: int = 0
    retrieved_bytes: int = 0
    expected_instances: Optional[int] = None
    download_artifacts: list[DownloadArtifact] = Field(default_factory=list)
    download_total_bytes: Optional[int] = None

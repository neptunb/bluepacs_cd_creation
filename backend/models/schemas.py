from pydantic import BaseModel
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


class BuildProgress(BaseModel):
    job_id: str
    status: str  # "queued", "retrieving", "building", "complete", "error"
    progress: float  # 0.0 to 1.0
    message: str
    filename: Optional[str] = None
    download_ready: bool = False
    retrieved_instances: int = 0
    expected_instances: Optional[int] = None

/** Cloudflare Access identity for header (GET /api/auth/identity). */
export interface AuthIdentity {
  display_name: string | null;
  email: string | null;
}

export interface DicomNode {
  ae_title: string;
  host: string;
  port: number;
  name: string | null;
}

export interface Patient {
  patient_id: string;
  patient_name: string;
  birth_date: string | null;
  sex: string | null;
}

export interface Study {
  study_instance_uid: string;
  study_date: string | null;
  study_time: string | null;
  study_description: string | null;
  accession_number: string | null;
  modalities_in_study: string | null;
  number_of_series: number | null;
  number_of_instances: number | null;
  patient_id: string;
  patient_name: string;
}

export interface Series {
  series_instance_uid: string;
  series_number: number | null;
  series_description: string | null;
  modality: string;
  number_of_instances: number | null;
  body_part_examined: string | null;
}

export interface BuildJob {
  job_id: string;
  status: "queued" | "retrieving" | "building" | "complete" | "error";
  progress: number;
  message: string;
  filename: string | null;
  download_ready: boolean;
  download_kind: "ohif_iso" | "study_zip";
  kpacs_filename: string | null;
  kpacs_download_ready: boolean;
  kpacs_error: string | null;
  retrieved_instances: number;
  expected_instances: number | null;
}

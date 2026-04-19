import axios from "axios";
import type {
  DicomNode,
  Patient,
  Study,
  Series,
  BuildJob,
  AuthIdentity,
} from "./types";

const apiPrefix =
  (typeof process !== "undefined" && process.env.NEXT_PUBLIC_CD_BASE_PATH) || "";

const api = axios.create({
  baseURL: `${apiPrefix}/api`,
  headers: { "Content-Type": "application/json" },
  withCredentials: true,
});

export const checkCdAccess = async (): Promise<boolean> => {
  try {
    const response = await api.get("/access");
    return response.status === 200 && response.data?.allowed === true;
  } catch {
    return false;
  }
};

export const fetchAuthIdentity = async (): Promise<AuthIdentity> => {
  const response = await axios.get<AuthIdentity>(`${apiPrefix}/cf-user`, {
    headers: { Accept: "application/json" },
    withCredentials: true,
  });
  return response.data;
};

export const fetchNodes = async (): Promise<DicomNode[]> => {
  const response = await api.get("/nodes/");
  return response.data.nodes;
};

export const echoNode = async (ae_title: string): Promise<boolean> => {
  const response = await api.post("/nodes/echo", { ae_title });
  return response.data.reachable;
};

export const searchPatients = async (params: {
  node_ae_title: string;
  patient_name?: string;
  patient_id?: string;
  study_date_from?: string;
  study_date_to?: string;
}): Promise<Patient[]> => {
  const response = await api.post("/patients/search", params);
  return response.data.patients;
};

export const fetchStudies = async (
  patient_id: string,
  node_ae_title: string,
  filters?: { modality?: string; study_date_from?: string; study_date_to?: string }
): Promise<Study[]> => {
  const response = await api.post(`/patients/${patient_id}/studies`, {
    node_ae_title,
    ...filters,
  });
  return response.data.studies;
};

export const fetchSeries = async (
  study_uid: string,
  node_ae_title: string
): Promise<Series[]> => {
  const response = await api.post(`/studies/${study_uid}/series`, {
    node_ae_title,
  });
  return response.data.series;
};

export const fetchRecentStudies = async (params: {
  node_ae_title: string;
  limit?: number;
  study_date_from?: string;
  study_date_to?: string;
}): Promise<Study[]> => {
  const response = await api.post("/studies/recent", {
    node_ae_title: params.node_ae_title,
    limit: params.limit ?? 10,
    ...(params.study_date_from != null && params.study_date_from !== ""
      ? { study_date_from: params.study_date_from }
      : {}),
    ...(params.study_date_to != null && params.study_date_to !== ""
      ? { study_date_to: params.study_date_to }
      : {}),
  });
  return response.data.studies;
};

export const createCd = async (params: {
  node_ae_title: string;
  patient_id: string;
  patient_name: string;
  studies: string[];
  series?: string[];
  expected_instances?: number;
  include_viewer?: boolean;
  include_macos_launcher?: boolean;
  include_windows_launcher?: boolean;
  include_linux_launcher?: boolean;
  include_kpacs?: boolean;
  study_zip_only?: boolean;
}): Promise<{ job_id: string }> => {
  const response = await api.post("/burn/create", params);
  return response.data;
};

export const getBuildStatus = async (job_id: string): Promise<BuildJob> => {
  const response = await api.get(`/burn/status/${job_id}`);
  return response.data;
};

export const getDownloadUrl = (job_id: string): string => {
  return `${apiPrefix}/api/burn/download/${job_id}`;
};

export const getKpacsDownloadUrl = (job_id: string): string => {
  return `${apiPrefix}/api/burn/download-kpacs/${job_id}`;
};

export const cleanupJob = async (job_id: string): Promise<void> => {
  await api.post(`/burn/cleanup/${job_id}`);
};

export default api;

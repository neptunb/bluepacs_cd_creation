import axios from "axios";
import type { DicomNode, Patient, Study, Series, BuildJob } from "./types";

const api = axios.create({
  baseURL: "/api",
  headers: { "Content-Type": "application/json" },
});

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
}): Promise<Study[]> => {
  const response = await api.post("/studies/recent", {
    node_ae_title: params.node_ae_title,
    limit: params.limit ?? 10,
  });
  return response.data.studies;
};

export const createCd = async (params: {
  node_ae_title: string;
  patient_id: string;
  patient_name: string;
  studies: string[];
  series?: string[];
  include_viewer?: boolean;
}): Promise<{ job_id: string }> => {
  const response = await api.post("/burn/create", params);
  return response.data;
};

export const getBuildStatus = async (job_id: string): Promise<BuildJob> => {
  const response = await api.get(`/burn/status/${job_id}`);
  return response.data;
};

export const getDownloadUrl = (job_id: string): string => {
  return `/api/burn/download/${job_id}`;
};

export const cleanupJob = async (job_id: string): Promise<void> => {
  await api.post(`/burn/cleanup/${job_id}`);
};

export default api;

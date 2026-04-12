import { create } from "zustand";
import type { DicomNode, Patient, Study, Series, BuildJob } from "@/lib/types";

export type RecentStudiesVariant = "latest10" | "lastWeek";

interface CdStore {
  nodes: DicomNode[];
  selectedNode: DicomNode | null;
  setNodes: (nodes: DicomNode[]) => void;
  setSelectedNode: (node: DicomNode | null) => void;

  patients: Patient[];
  selectedPatient: Patient | null;
  patientSearchLoading: boolean;
  setPatients: (patients: Patient[]) => void;
  setSelectedPatient: (patient: Patient | null) => void;
  setPatientSearchLoading: (loading: boolean) => void;

  studies: Study[];
  selectedStudies: string[];
  studiesLoading: boolean;
  latestStudiesMode: boolean;
  recentStudiesVariant: RecentStudiesVariant | null;
  setStudies: (studies: Study[]) => void;
  loadLatestStudies: (studies: Study[], variant: RecentStudiesVariant) => void;
  toggleStudySelection: (studyUid: string) => void;
  selectAllStudies: () => void;
  clearStudySelection: () => void;
  setStudiesLoading: (loading: boolean) => void;

  seriesMap: Record<string, Series[]>;
  selectedSeries: string[];
  setSeriesForStudy: (studyUid: string, series: Series[]) => void;
  toggleSeriesSelection: (seriesUid: string) => void;
  setSelectedSeries: (series: string[]) => void;

  buildJob: BuildJob | null;
  setBuildJob: (job: BuildJob | null) => void;

  reset: () => void;
}

export const useCdStore = create<CdStore>((set, get) => ({
  nodes: [],
  selectedNode: null,
  setNodes: (nodes) => set({ nodes }),
  setSelectedNode: (node) => set({ selectedNode: node }),

  patients: [],
  selectedPatient: null,
  patientSearchLoading: false,
  setPatients: (patients) => set({ patients }),
  setSelectedPatient: (patient) =>
    set({
      selectedPatient: patient,
      studies: [],
      selectedStudies: [],
      seriesMap: {},
      selectedSeries: [],
      latestStudiesMode: false,
      recentStudiesVariant: null,
    }),
  setPatientSearchLoading: (loading) => set({ patientSearchLoading: loading }),

  studies: [],
  selectedStudies: [],
  studiesLoading: false,
  latestStudiesMode: false,
  recentStudiesVariant: null,
  setStudies: (studies) => set({ studies }),
  loadLatestStudies: (studies, variant) =>
    set({
      latestStudiesMode: true,
      recentStudiesVariant: variant,
      selectedPatient: null,
      studies,
      selectedStudies: [],
      seriesMap: {},
      selectedSeries: [],
    }),
  toggleStudySelection: (studyUid) => {
    const current = get().selectedStudies;
    if (current.includes(studyUid)) {
      set({ selectedStudies: current.filter((uid) => uid !== studyUid) });
    } else {
      set({ selectedStudies: [...current, studyUid] });
    }
  },
  selectAllStudies: () => {
    set({ selectedStudies: get().studies.map((s) => s.study_instance_uid) });
  },
  clearStudySelection: () => set({ selectedStudies: [] }),
  setStudiesLoading: (loading) => set({ studiesLoading: loading }),

  seriesMap: {},
  selectedSeries: [],
  setSeriesForStudy: (studyUid, series) =>
    set((state) => ({
      seriesMap: { ...state.seriesMap, [studyUid]: series },
    })),
  toggleSeriesSelection: (seriesUid) => {
    const current = get().selectedSeries;
    if (current.includes(seriesUid)) {
      set({ selectedSeries: current.filter((uid) => uid !== seriesUid) });
    } else {
      set({ selectedSeries: [...current, seriesUid] });
    }
  },
  setSelectedSeries: (series) => set({ selectedSeries: series }),

  buildJob: null,
  setBuildJob: (job) => set({ buildJob: job }),

  reset: () =>
    set({
      patients: [],
      selectedPatient: null,
      studies: [],
      selectedStudies: [],
      seriesMap: {},
      selectedSeries: [],
      buildJob: null,
      latestStudiesMode: false,
      recentStudiesVariant: null,
    }),
}));

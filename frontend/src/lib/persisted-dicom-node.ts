/** localStorage key for last chosen PACS node (AE Title). */
export const LAST_DICOM_NODE_AE_KEY = "bluepacs-cd-last-dicom-node-ae";

export const readLastSelectedDicomNodeAe = (): string | null => {
  if (typeof window === "undefined") return null;
  try {
    const v = localStorage.getItem(LAST_DICOM_NODE_AE_KEY);
    return v?.trim() || null;
  } catch {
    return null;
  }
};

export const writeLastSelectedDicomNodeAe = (aeTitle: string): void => {
  if (typeof window === "undefined") return;
  try {
    localStorage.setItem(LAST_DICOM_NODE_AE_KEY, aeTitle.trim());
  } catch {
    // private mode / quota — ignore
  }
};

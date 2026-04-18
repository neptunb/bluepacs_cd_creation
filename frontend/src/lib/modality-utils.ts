/**
 * Parse ModalitiesInStudy for display and token matching (e.g. modality column).
 * Handles DICOM backslash form (CT\\MR), commas, and Python/JSON-ish list strings
 * like "['DOC', 'NM', 'OT']" from some PACS / pydicom str(MultiValue) paths.
 */
export const modalitiesTokens = (
  modalitiesInStudy: string | null | undefined
): string[] => {
  if (!modalitiesInStudy?.trim()) return [];
  const raw = modalitiesInStudy.trim();
  if (raw.startsWith("[") && raw.endsWith("]")) {
    const inner = raw.slice(1, -1).trim();
    return inner
      .split(",")
      .map((t) => t.trim().replace(/^['"]+|['"]+$/g, ""))
      .map((t) => t.toUpperCase())
      .filter(Boolean);
  }
  return raw
    .toUpperCase()
    .split(/[\\/,;\s]+/)
    .map((t) => t.trim())
    .filter(Boolean);
};

/** Human-readable modality column (comma-separated CS values). */
export const formatModalitiesLabel = (
  modalitiesInStudy: string | null | undefined
): string => {
  const tokens = modalitiesTokens(modalitiesInStudy);
  if (tokens.length > 0) return tokens.join(", ");
  const s = modalitiesInStudy?.trim();
  return s && s.length > 0 ? s : "—";
};

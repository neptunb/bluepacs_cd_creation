"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { useTranslations } from "next-intl";
import {
  Paper,
  Typography,
  Button,
  Box,
  LinearProgress,
  Alert,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Divider,
  Checkbox,
  FormControlLabel,
} from "@mui/material";
import AlbumIcon from "@mui/icons-material/Album";
import DownloadIcon from "@mui/icons-material/Download";
import CloudDownloadIcon from "@mui/icons-material/CloudDownload";
import CheckCircleIcon from "@mui/icons-material/CheckCircle";
import ErrorIcon from "@mui/icons-material/Error";
import LocalFireDepartmentIcon from "@mui/icons-material/LocalFireDepartment";
import FolderZipIcon from "@mui/icons-material/FolderZip";
import { useCdStore } from "@/store/use-cd-store";
import {
  createCd,
  getBuildStatus,
  getDownloadUrl,
  getKpacsDownloadUrl,
  cleanupJob,
} from "@/lib/api";
import type { Study, Series } from "@/lib/types";
import type { SxProps, Theme } from "@mui/material/styles";

const BUILD_STATUSES = [
  "queued",
  "retrieving",
  "building",
  "complete",
  "error",
] as const;

type BuildStatusKey = (typeof BUILD_STATUSES)[number];

const isBuildStatusKey = (s: string): s is BuildStatusKey =>
  (BUILD_STATUSES as readonly string[]).includes(s);

/** Parantez içi MB: her durumda aynı soluk ton (seçim / disabled ile değişmez) */
const viewerSizeNoteColor = (theme: Theme) =>
  theme.palette.mode === "dark"
    ? "rgba(255, 255, 255, 0.3)"
    : "rgba(0, 0, 0, 0.3)";

const viewerFormControlLabelSx = (theme: Theme) => ({
  marginLeft: 0,
  alignItems: "center",
  "&.Mui-disabled": {
    opacity: 1,
  },
  "& .MuiFormControlLabel-label": {
    fontSize: "1.125rem",
    lineHeight: 1.5,
    color: theme.palette.text.primary,
  },
  "& .MuiCheckbox-root.Mui-disabled": {
    opacity: 0.55,
  },
  "& .burn-panel-viewer-size-note, &.Mui-disabled .burn-panel-viewer-size-note": {
    color: `${viewerSizeNoteColor(theme)} !important`,
    opacity: "1 !important",
  },
});

const decimalsForValue = (value: number): number => {
  if (value >= 100) return 0;
  if (value >= 10) return 1;
  return 2;
};

const formatBytes = (bytes: number): string => {
  if (!Number.isFinite(bytes) || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes;
  let i = 0;
  while (value >= 1024 && i < units.length - 1) {
    value /= 1024;
    i += 1;
  }
  return `${value.toFixed(decimalsForValue(value))} ${units[i]}`;
};

const formatSpeed = (bytesPerSecond: number | null): string | null => {
  if (bytesPerSecond === null || !Number.isFinite(bytesPerSecond) || bytesPerSecond < 1) {
    return null;
  }
  return `${formatBytes(bytesPerSecond)}/s`;
};

/** Parse Content-Length safely for multi-GB files (avoid parseInt quirks; stay within Number.isSafeInteger). */
const parseContentLengthBytes = (raw: string | null): number | null => {
  if (!raw) return null;
  const n = Number(String(raw).trim());
  if (!Number.isFinite(n) || n <= 0 || n > Number.MAX_SAFE_INTEGER) return null;
  return Math.floor(n);
};

/** Stream the URL with cookies without buffering the whole body in JS (needed for files well above ~2GB on Windows/macOS). */
const triggerBrowserNativeDownload = (url: string, filename: string): void => {
  if (typeof document === "undefined") return;
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.rel = "noopener";
  anchor.style.display = "none";
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
};

/**
 * When the browser owns the download we disable the button; MUI's default disabled
 * styling is too low-contrast — keep label and icon clearly readable.
 */
const browserHandoffContainedButtonSx = (
  apply: boolean,
  color: "success" | "primary",
): SxProps<Theme> | undefined => {
  if (!apply) return undefined;
  return (theme: Theme) => {
    const softBg =
      color === "success"
        ? theme.palette.success.light
        : theme.palette.primary.light;
    const iconColor =
      color === "success"
        ? theme.palette.success.dark
        : theme.palette.primary.dark;
    return {
      "&.Mui-disabled": {
        opacity: 1,
        color: theme.palette.text.primary,
        WebkitTextFillColor: theme.palette.text.primary,
        backgroundColor: softBg,
        "& .MuiSvgIcon-root": {
          color: iconColor,
        },
        boxShadow: "none",
      },
    };
  };
};

/** Prefer series-level instance totals when the study-level C-FIND count is missing or too low (some PACS). */
const expectedInstancesForSelection = (
  selectedStudyUids: string[],
  studies: Study[],
  seriesMap: Record<string, Series[]>,
  selectedSeriesUids: string[],
): number => {
  return selectedStudyUids.reduce((sum, studyUid) => {
    const study = studies.find((s) => s.study_instance_uid === studyUid);
    const fromStudy = study?.number_of_instances ?? 0;
    const seriesList = seriesMap[studyUid];
    let fromSeries = 0;
    if (seriesList?.length) {
      const rows =
        selectedSeriesUids.length > 0
          ? seriesList.filter((s) =>
              selectedSeriesUids.includes(s.series_instance_uid),
            )
          : seriesList;
      fromSeries = rows.reduce((acc, s) => acc + (s.number_of_instances ?? 0), 0);
    }
    const part =
      fromSeries > fromStudy
        ? fromSeries
        : fromStudy > 0
          ? fromStudy
          : fromSeries;
    return sum + part;
  }, 0);
};

const viewerLabelWithSize = (title: string, sizeLabel: string) => (
  <Box
    component="span"
    sx={{
      display: "inline-flex",
      flexWrap: "wrap",
      alignItems: "baseline",
      columnGap: 0.5,
      rowGap: 0.25,
    }}
  >
    <Box component="span" sx={{ color: "inherit" }}>
      {title}
    </Box>
    <Box
      component="span"
      className="burn-panel-viewer-size-note"
      sx={(theme) => ({
        color: viewerSizeNoteColor(theme),
        opacity: 1,
        fontWeight: 400,
        fontSize: "0.86em",
      })}
    >
      {sizeLabel}
    </Box>
  </Box>
);

const BurnPanel = () => {
  const t = useTranslations("burnPanel");
  const tStatus = useTranslations("burnPanel.status");
  const {
    selectedNode,
    selectedPatient,
    studies,
    selectedStudies,
    selectedSeries,
    seriesMap,
    buildJob,
    setBuildJob,
  } = useCdStore();

  const [dialogOpen, setDialogOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [includeWindowsLauncher, setIncludeWindowsLauncher] = useState(true);
  const [includeMacosLauncher, setIncludeMacosLauncher] = useState(false);
  const [includeLinuxLauncher, setIncludeLinuxLauncher] = useState(false);
  const [downloadSpeedBps, setDownloadSpeedBps] = useState<number | null>(null);
  const [downloadKind, setDownloadKind] = useState<"iso" | "kpacs" | null>(null);
  const [downloadReceivedBytes, setDownloadReceivedBytes] = useState(0);
  const [downloadTotalBytes, setDownloadTotalBytes] = useState<number | null>(null);
  const [downloadSpeedPhaseBps, setDownloadSpeedPhaseBps] = useState<number | null>(null);
  const [completedDownloads, setCompletedDownloads] = useState<{
    iso?: number;
    kpacs?: number;
  }>({});
  /** Browser-native download started for OHIF/ZIP (shared slot uses "iso"). */
  const [nativeHandoffIso, setNativeHandoffIso] = useState(false);
  /** Browser-native download started for K-PACS ISO. */
  const [nativeHandoffKpacs, setNativeHandoffKpacs] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const speedSampleRef = useRef<{ t: number; bytes: number } | null>(null);
  const downloadAbortRef = useRef<AbortController | null>(null);
  const downloadSpeedSampleRef = useRef<{ t: number; bytes: number } | null>(null);

  const firstSelectedStudy = studies.find((s) =>
    selectedStudies.includes(s.study_instance_uid)
  );
  const burnPatientId =
    selectedPatient?.patient_id ?? firstSelectedStudy?.patient_id ?? "";
  const burnPatientName =
    selectedPatient?.patient_name ?? firstSelectedStudy?.patient_name ?? "";
  const expectedInstances = expectedInstancesForSelection(
    selectedStudies,
    studies,
    seriesMap,
    selectedSeries,
  );

  const canBuild =
    Boolean(selectedNode) &&
    selectedStudies.length > 0 &&
    Boolean(burnPatientId);

  const anyIsoViewer =
    includeWindowsLauncher || includeMacosLauncher || includeLinuxLauncher;

  const resetBrowserHandoffUi = useCallback(() => {
    setNativeHandoffIso(false);
    setNativeHandoffKpacs(false);
  }, []);

  const startBuild = useCallback(
    async (opts: { studyZipOnly: boolean }) => {
      if (!selectedNode || !burnPatientId) return;

      setError(null);
      setDialogOpen(true);
      speedSampleRef.current = null;
      setDownloadSpeedBps(null);
      setCompletedDownloads({});
      resetBrowserHandoffUi();

      try {
        const isoViewers =
          !opts.studyZipOnly &&
          (includeWindowsLauncher || includeMacosLauncher || includeLinuxLauncher);
        const { job_id } = await createCd({
          node_ae_title: selectedNode.ae_title,
          patient_id: burnPatientId,
          patient_name: burnPatientName || t("patientFallback"),
          studies: selectedStudies,
          series: selectedSeries.length > 0 ? selectedSeries : undefined,
          expected_instances: expectedInstances > 0 ? expectedInstances : undefined,
          include_viewer: opts.studyZipOnly ? true : isoViewers,
          include_macos_launcher:
            !opts.studyZipOnly && includeMacosLauncher,
          include_windows_launcher:
            !opts.studyZipOnly && includeWindowsLauncher,
          include_linux_launcher:
            !opts.studyZipOnly && includeLinuxLauncher,
          include_kpacs:
            !opts.studyZipOnly && includeWindowsLauncher,
          study_zip_only: opts.studyZipOnly,
        });

        setBuildJob({
          job_id,
          status: "queued",
          progress: 0,
          message: t("jobQueued"),
          filename: null,
          download_ready: false,
          download_kind: opts.studyZipOnly ? "study_zip" : "ohif_iso",
          kpacs_filename: null,
          kpacs_download_ready: false,
          kpacs_error: null,
          retrieved_instances: 0,
          retrieved_bytes: 0,
          expected_instances: expectedInstances > 0 ? expectedInstances : null,
          download_artifacts: [],
          download_total_bytes: null,
        });

        let consecutivePollErrors = 0;
        pollRef.current = setInterval(async () => {
          try {
            const status = await getBuildStatus(job_id);
            consecutivePollErrors = 0;
            setBuildJob(status);
            if (status.status === "complete" || status.status === "error") {
              if (pollRef.current) clearInterval(pollRef.current);
            }
          } catch (pollErr) {
            consecutivePollErrors += 1;
            if (consecutivePollErrors >= 5) {
              console.error("Build status polling failed repeatedly", pollErr);
              if (pollRef.current) clearInterval(pollRef.current);
            }
          }
        }, 2000);
      } catch (err) {
        console.error("Failed to start build:", err);
        setError(
          opts.studyZipOnly ? t("errorStartZip") : t("errorStartIso")
        );
      }
    },
    [
      selectedNode,
      burnPatientId,
      burnPatientName,
      expectedInstances,
      selectedStudies,
      selectedSeries,
      seriesMap,
      setBuildJob,
      t,
      includeWindowsLauncher,
      includeMacosLauncher,
      includeLinuxLauncher,
      resetBrowserHandoffUi,
    ]
  );

  const parseFilenameFromDisposition = (
    disposition: string | null,
    fallback: string,
  ): string => {
    if (!disposition) return fallback;
    const starMatch = /filename\*\s*=\s*(?:UTF-8'')?([^;\r\n"']+)/i.exec(
      disposition,
    );
    if (starMatch?.[1]) {
      try {
        return decodeURIComponent(starMatch[1].trim());
      } catch {
        return starMatch[1].trim();
      }
    }
    const plainMatch = /filename\s*=\s*"?([^";\r\n]+)"?/i.exec(disposition);
    return plainMatch?.[1]?.trim() || fallback;
  };

  const streamDownloadFile = useCallback(
    async (
      url: string,
      fallbackName: string,
      kind: "iso" | "kpacs",
    ): Promise<void> => {
      downloadAbortRef.current?.abort();
      const ac = new AbortController();
      downloadAbortRef.current = ac;

      setError(null);
      setDownloadKind(kind);
      setDownloadReceivedBytes(0);
      setDownloadTotalBytes(null);
      setDownloadSpeedPhaseBps(null);
      downloadSpeedSampleRef.current = null;

      try {
        const canUseSavePicker =
          typeof window !== "undefined" &&
          typeof window.showSaveFilePicker === "function";

        const applyDownloadSpeedSample = (received: number) => {
          const now = Date.now();
          const prev = downloadSpeedSampleRef.current;
          if (!prev) {
            downloadSpeedSampleRef.current = { t: now, bytes: received };
          } else {
            const dt = (now - prev.t) / 1000;
            if (dt >= 0.4) {
              const instant = (received - prev.bytes) / dt;
              setDownloadSpeedPhaseBps((current) =>
                current === null ? instant : current * 0.5 + instant * 0.5,
              );
              downloadSpeedSampleRef.current = { t: now, bytes: received };
            }
          }
        };

        if (!canUseSavePicker) {
          const probeResp = await fetch(url, {
            credentials: "include",
            signal: ac.signal,
            cache: "no-store",
          });
          if (!probeResp.ok) {
            throw new Error(`Download failed (HTTP ${probeResp.status})`);
          }
          const total = parseContentLengthBytes(
            probeResp.headers.get("Content-Length"),
          );
          const filename = parseFilenameFromDisposition(
            probeResp.headers.get("Content-Disposition"),
            fallbackName,
          );
          setDownloadTotalBytes(total);
          await probeResp.body?.cancel().catch(() => undefined);
          triggerBrowserNativeDownload(url, filename);
          if (kind === "iso") setNativeHandoffIso(true);
          else setNativeHandoffKpacs(true);
          return;
        }

        const resp = await fetch(url, {
          credentials: "include",
          signal: ac.signal,
          cache: "no-store",
        });
        if (!resp.ok || !resp.body) {
          throw new Error(`Download failed (HTTP ${resp.status})`);
        }

        const total = parseContentLengthBytes(resp.headers.get("Content-Length"));
        setDownloadTotalBytes(total);
        const filename = parseFilenameFromDisposition(
          resp.headers.get("Content-Disposition"),
          fallbackName,
        );

        const isZip = fallbackName.toLowerCase().endsWith(".zip");

        const savePicker = window.showSaveFilePicker;
        if (!savePicker) {
          await resp.body.cancel().catch(() => undefined);
          triggerBrowserNativeDownload(url, filename);
          if (kind === "iso") setNativeHandoffIso(true);
          else setNativeHandoffKpacs(true);
          return;
        }

        let streamReader: ReadableStreamDefaultReader<Uint8Array> | null = null;
        try {
          const handle = await savePicker({
            suggestedName: filename,
            types: [
              {
                description: isZip ? "ZIP archive" : "Disc image",
                accept: isZip
                  ? { "application/zip": [".zip"] }
                  : { "application/x-iso9660-image": [".iso"] },
              },
            ],
          });
          const writable = await handle.createWritable();
          streamReader = resp.body.getReader();
          let received = 0;
          while (true) {
            const { value, done } = await streamReader.read();
            if (done) break;
            if (!value) continue;
            await writable.write(value as BufferSource);
            received += value.byteLength;
            setDownloadReceivedBytes(received);
            applyDownloadSpeedSample(received);
          }
          await writable.close();
          const outFile = await handle.getFile();
          if (kind === "iso") setNativeHandoffIso(false);
          else setNativeHandoffKpacs(false);
          setCompletedDownloads((prev) => ({ ...prev, [kind]: outFile.size }));
          return;
        } catch (pickerErr) {
          await streamReader?.cancel().catch(() => undefined);
          if ((pickerErr as { name?: string })?.name === "AbortError") {
            await resp.body?.cancel().catch(() => undefined);
            return;
          }
          console.warn(
            "Save-file picker or disk write failed; using browser native download",
            pickerErr,
          );
          await resp.body?.cancel().catch(() => undefined);
          triggerBrowserNativeDownload(url, filename);
          if (kind === "iso") setNativeHandoffIso(true);
          else setNativeHandoffKpacs(true);
          return;
        }
      } catch (err) {
        if ((err as { name?: string })?.name === "AbortError") return;
        console.error("Streaming download failed:", err);
        setError(t("errorDownload"));
      } finally {
        if (downloadAbortRef.current === ac) {
          downloadAbortRef.current = null;
        }
        setDownloadKind(null);
        setDownloadSpeedPhaseBps(null);
        downloadSpeedSampleRef.current = null;
      }
    },
    [t],
  );

  const handleDownload = useCallback(() => {
    if (!buildJob?.job_id) return;
    const fallback =
      buildJob.filename ||
      (buildJob.download_kind === "study_zip"
        ? "dicom_images.zip"
        : "dicom_images.iso");
    void streamDownloadFile(getDownloadUrl(buildJob.job_id), fallback, "iso");
  }, [buildJob, streamDownloadFile]);

  const handleDownloadKpacs = useCallback(() => {
    if (!buildJob?.job_id) return;
    const fallback = buildJob.kpacs_filename || "kpacs_disc.iso";
    void streamDownloadFile(
      getKpacsDownloadUrl(buildJob.job_id),
      fallback,
      "kpacs",
    );
  }, [buildJob, streamDownloadFile]);

  const handleClose = useCallback(async () => {
    downloadAbortRef.current?.abort();
    downloadAbortRef.current = null;
    if (buildJob?.job_id) {
      try {
        await cleanupJob(buildJob.job_id);
      } catch {
        // server cleanup is best-effort
      }
    }
    setDialogOpen(false);
    setBuildJob(null);
    speedSampleRef.current = null;
    setDownloadSpeedBps(null);
    setDownloadKind(null);
    setDownloadReceivedBytes(0);
    setDownloadTotalBytes(null);
    setDownloadSpeedPhaseBps(null);
    setCompletedDownloads({});
    resetBrowserHandoffUi();
    downloadSpeedSampleRef.current = null;
  }, [buildJob, setBuildJob, resetBrowserHandoffUi]);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      downloadAbortRef.current?.abort();
    };
  }, []);

  useEffect(() => {
    if (!buildJob) {
      speedSampleRef.current = null;
      setDownloadSpeedBps(null);
      return;
    }
    if (buildJob.status !== "retrieving") {
      speedSampleRef.current = null;
      setDownloadSpeedBps(null);
      return;
    }
    const bytes = buildJob.retrieved_bytes ?? 0;
    const now = Date.now();
    const prev = speedSampleRef.current;
    if (prev && now > prev.t) {
      const deltaSeconds = (now - prev.t) / 1000;
      const deltaBytes = bytes - prev.bytes;
      if (deltaSeconds >= 0.25 && deltaBytes >= 0) {
        const instant = deltaBytes / deltaSeconds;
        setDownloadSpeedBps((current) =>
          current === null ? instant : current * 0.5 + instant * 0.5
        );
        speedSampleRef.current = { t: now, bytes };
      }
    } else {
      speedSampleRef.current = { t: now, bytes };
    }
  }, [buildJob]);

  const statusColor = (status: string) => {
    switch (status) {
      case "complete": return "success" as const;
      case "error": return "error" as const;
      case "retrieving":
      case "building": return "warning" as const;
      default: return "default" as const;
    }
  };
  const getStatusIcon = (status?: string) => {
    if (status === "complete") return <CheckCircleIcon />;
    if (status === "error") return <ErrorIcon />;
    return undefined;
  };

  return (
    <>
      <Paper
        className="p-4 md:p-5"
        sx={{ color: "text.primary" }}
      >
        <Typography
          variant="h6"
          component="h2"
          className="mb-4 md:mb-5 flex items-center gap-2"
          sx={{
            fontSize: { xs: "1.3rem", md: "1.4rem" },
            fontWeight: 600,
            lineHeight: 1.35,
            color: "text.primary",
          }}
        >
          <AlbumIcon
            sx={{ fontSize: { xs: "1.5rem", md: "1.65rem" }, color: "text.primary" }}
            aria-hidden
          />{" "}
          {t("title")}
        </Typography>

        <Box className="flex flex-col md:flex-row md:items-start md:gap-8 lg:gap-10 gap-6">
          <Box className="flex-1 min-w-0 flex flex-col gap-4 md:gap-5">
            <Box
              role="group"
              aria-label={t("viewerOptionsGroupAria")}
              className="flex flex-col gap-2 pl-0.5"
            >
              <FormControlLabel
                className="m-0 py-0.5"
                sx={viewerFormControlLabelSx}
                control={
                  <Checkbox
                    size="medium"
                    checked={includeWindowsLauncher}
                    onChange={(e) =>
                      setIncludeWindowsLauncher(e.target.checked)
                    }
                    disabled={!canBuild}
                    aria-label={t("viewerWindowsAria")}
                  />
                }
                label={viewerLabelWithSize(
                  t("viewerWindows"),
                  t("viewerWindowsSize"),
                )}
              />
              <FormControlLabel
                className="m-0 py-0.5"
                sx={viewerFormControlLabelSx}
                control={
                  <Checkbox
                    size="medium"
                    checked={includeMacosLauncher}
                    onChange={(e) => setIncludeMacosLauncher(e.target.checked)}
                    disabled={!canBuild}
                    aria-label={t("viewerMacosAria")}
                  />
                }
                label={viewerLabelWithSize(
                  t("viewerMacos"),
                  t("viewerMacosSize"),
                )}
              />
              <FormControlLabel
                className="m-0 py-0.5"
                sx={viewerFormControlLabelSx}
                control={
                  <Checkbox
                    size="medium"
                    checked={includeLinuxLauncher}
                    onChange={(e) => setIncludeLinuxLauncher(e.target.checked)}
                    disabled={!canBuild}
                    aria-label={t("viewerLinuxAria")}
                  />
                }
                label={viewerLabelWithSize(
                  t("viewerLinux"),
                  t("viewerLinuxSize"),
                )}
              />
            </Box>

            <Box className="flex items-center gap-3 md:gap-4 flex-wrap">
              <Typography
                variant="body1"
                sx={{
                  fontSize: "1.125rem",
                  lineHeight: 1.55,
                  fontWeight: 600,
                  color: "text.primary",
                }}
              >
                {t("studiesSelected", { count: selectedStudies.length })}
              </Typography>

              <Button
                variant="contained"
                color="secondary"
                size="large"
                startIcon={<FolderZipIcon />}
                onClick={() => {
                  startBuild({ studyZipOnly: true }).catch(console.error);
                }}
                disabled={!canBuild}
                className="cursor-pointer"
                aria-label={t("downloadStudyZipAria")}
                sx={{
                  fontSize: "1.0625rem",
                  py: 1.25,
                  px: 2.5,
                  minHeight: 48,
                  textTransform: "none",
                }}
              >
                {t("downloadStudyZip")}
              </Button>

              <Button
                variant="contained"
                color="primary"
                size="large"
                startIcon={<LocalFireDepartmentIcon />}
                onClick={() => {
                  startBuild({ studyZipOnly: false }).catch(console.error);
                }}
                disabled={!canBuild || !anyIsoViewer}
                className="cursor-pointer"
                aria-label={t("buildIsoAria")}
                sx={{
                  fontSize: "1.0625rem",
                  py: 1.25,
                  px: 2.5,
                  minHeight: 48,
                  textTransform: "none",
                }}
              >
                {t("buildIso")}
              </Button>
            </Box>
          </Box>

          <Box
            className="flex-1 min-w-0 md:max-w-[min(28rem,48%)] md:shrink-0"
            component="aside"
            aria-label={t("hintZipAria")}
          >
            <Box
              sx={(theme) => ({
                borderRadius: 2,
                borderWidth: 2,
                borderStyle: "solid",
                borderColor: theme.palette.grey[600],
                bgcolor: theme.palette.common.white,
                color: theme.palette.grey[900],
                px: 2.5,
                py: 2,
                boxShadow: "0 2px 8px rgba(0, 0, 0, 0.1)",
              })}
            >
              <Typography
                variant="body1"
                component="p"
                sx={(theme) => ({
                  m: 0,
                  fontSize: "1.0625rem",
                  lineHeight: 1.75,
                  fontWeight: 400,
                  color: theme.palette.grey[900],
                  whiteSpace: "pre-line",
                })}
              >
                {t("hintZip")}
              </Typography>
            </Box>
          </Box>
        </Box>

        {error && (
          <Alert severity="error" className="mt-4" role="alert">
            {error}
          </Alert>
        )}
      </Paper>

      <Dialog
        open={dialogOpen}
        onClose={() => {
          if (downloadKind !== null) return;
          if (buildJob?.status === "complete" || buildJob?.status === "error") {
            handleClose();
          }
        }}
        maxWidth="sm"
        fullWidth
        aria-labelledby="build-dialog-title"
      >
        <DialogTitle id="build-dialog-title">
          {buildJob?.download_kind === "study_zip"
            ? t("dialogTitleZip")
            : t("dialogTitleIso")}
        </DialogTitle>
        <DialogContent>
          {buildJob && (
            <Box className="space-y-4 py-2">
              <Box className="flex items-center gap-2">
                <Typography variant="body2">{t("statusLabel")}</Typography>
                <Chip
                  label={
                    isBuildStatusKey(buildJob.status)
                      ? tStatus(buildJob.status)
                      : buildJob.status
                  }
                  color={statusColor(buildJob.status)}
                  size="small"
                  icon={getStatusIcon(buildJob.status)}
                />
              </Box>

              {(() => {
                const isDownloading = downloadKind !== null;
                const knownTotal =
                  downloadTotalBytes !== null && downloadTotalBytes > 0;
                const downloadRatio =
                  isDownloading && knownTotal && downloadTotalBytes
                    ? Math.min(1, downloadReceivedBytes / downloadTotalBytes)
                    : null;
                const barValue =
                  isDownloading && downloadRatio !== null
                    ? downloadRatio * 100
                    : buildJob.progress * 100;
                // Tarayıcıya devredildikten sonra indirme bitişini bilemeyiz; indeterminate
                // çubuğu sonsuz döner — bu yüzden burada sadece iş (buildJob.progress) kullanılır.
                const useIndeterminate =
                  isDownloading && downloadRatio === null;

                return (
                  <LinearProgress
                    variant={useIndeterminate ? "indeterminate" : "determinate"}
                    value={useIndeterminate ? undefined : barValue}
                    className="rounded"
                    aria-label={t("progressAria")}
                    aria-valuenow={useIndeterminate ? undefined : barValue}
                    aria-valuemin={0}
                    aria-valuemax={100}
                  />
                );
              })()}

              <Typography variant="body2" className="text-gray-600">
                {downloadKind !== null
                  ? t(
                      downloadKind === "kpacs"
                        ? "downloadingKpacs"
                        : "downloadingIso",
                    )
                  : nativeHandoffIso || nativeHandoffKpacs
                    ? t("downloadSentToBrowserStatus")
                    : buildJob.message}
              </Typography>
              <Typography variant="body2" className="text-gray-700 font-medium">
                {t("retrievedInstances", {
                  count: buildJob.retrieved_instances,
                })}
              </Typography>
              {(buildJob.status === "retrieving" ||
                (buildJob.retrieved_bytes ?? 0) > 0) && (
                <Typography
                  variant="body2"
                  className="text-gray-700 font-medium"
                  aria-live="polite"
                >
                  {(() => {
                    const speedLabel = formatSpeed(downloadSpeedBps);
                    const transferred = formatBytes(
                      buildJob.retrieved_bytes ?? 0,
                    );
                    if (buildJob.status === "retrieving" && speedLabel) {
                      return t("transferSpeed", {
                        speed: speedLabel,
                        transferred,
                      });
                    }
                    return t("transferred", { transferred });
                  })()}
                </Typography>
              )}
              {buildJob.status === "complete" &&
                (buildJob.download_artifacts?.length ?? 0) > 0 && (
                  <Box
                    component="div"
                    className="mt-1 flex flex-col gap-0.5"
                    aria-label={t("downloadOutputsHeading")}
                  >
                    <Typography
                      variant="body2"
                      className="text-gray-800 font-semibold"
                    >
                      {t("downloadOutputsHeading")}
                    </Typography>
                    <Box
                      component="ul"
                      className="m-0 list-none space-y-0.5 pl-0"
                    >
                      {(buildJob.download_artifacts ?? []).map((a) => (
                        <Box
                          component="li"
                          key={a.filename}
                          className="text-gray-700 text-sm"
                        >
                          <Typography variant="body2" component="span">
                            {t("downloadOutputRow", {
                              name: a.filename,
                              fileSize: formatBytes(a.size),
                            })}
                          </Typography>
                        </Box>
                      ))}
                    </Box>
                    {buildJob.download_total_bytes != null &&
                      buildJob.download_total_bytes > 0 && (
                        <Typography
                          variant="body2"
                          className="text-gray-800 font-medium mt-0.5"
                        >
                          {t("downloadTotalDownloadable", {
                            total: formatBytes(buildJob.download_total_bytes),
                          })}
                        </Typography>
                      )}
                  </Box>
                )}
              {downloadKind !== null && (
                <Typography
                  variant="body2"
                  className="text-gray-700 font-medium"
                  aria-live="polite"
                >
                  {(() => {
                    const speedLabel = formatSpeed(downloadSpeedPhaseBps);
                    const transferred = formatBytes(downloadReceivedBytes);
                    const total =
                      downloadTotalBytes !== null && downloadTotalBytes > 0
                        ? formatBytes(downloadTotalBytes)
                        : null;
                    if (total && speedLabel) {
                      return t("downloadSpeedWithTotal", {
                        speed: speedLabel,
                        transferred,
                        total,
                      });
                    }
                    if (total) {
                      return t("downloadTotal", { transferred, total });
                    }
                    if (speedLabel) {
                      return t("downloadSpeed", { speed: speedLabel, transferred });
                    }
                    return t("downloaded", { transferred });
                  })()}
                </Typography>
              )}
              {downloadKind === null &&
                (completedDownloads.iso !== undefined ||
                  completedDownloads.kpacs !== undefined) && (
                  <Box className="flex flex-col gap-0.5">
                    {completedDownloads.iso !== undefined && (
                      <Typography
                        variant="body2"
                        className="text-gray-700 font-medium"
                      >
                        {t("downloadedIsoSize", {
                          transferred: formatBytes(completedDownloads.iso),
                        })}
                      </Typography>
                    )}
                    {completedDownloads.kpacs !== undefined && (
                      <Typography
                        variant="body2"
                        className="text-gray-700 font-medium"
                      >
                        {t("downloadedKpacsSize", {
                          transferred: formatBytes(completedDownloads.kpacs),
                        })}
                      </Typography>
                    )}
                  </Box>
                )}

              {(nativeHandoffIso || nativeHandoffKpacs) && (
                <Alert
                  id="burn-browser-handoff-help"
                  severity="info"
                  className="mt-1"
                  role="status"
                >
                  <Typography variant="body2">
                    {t("downloadSentToBrowserHelp")}
                  </Typography>
                </Alert>
              )}

              {buildJob.download_ready && (
                <>
                  <Divider />
                  {buildJob.download_kind === "study_zip" ? (
                    <>
                      <Alert severity="success" icon={<CheckCircleIcon />}>
                        <Typography variant="body2" className="font-medium">
                          {buildJob.filename}
                        </Typography>
                        <Typography variant="body2" className="mt-1">
                          {t("zipReadyBody")}
                        </Typography>
                      </Alert>
                      <Button
                        variant="contained"
                        color="success"
                        size="large"
                        fullWidth
                        startIcon={
                          completedDownloads.iso !== undefined ? (
                            <CheckCircleIcon />
                          ) : nativeHandoffIso ? (
                            <CloudDownloadIcon />
                          ) : (
                            <DownloadIcon />
                          )
                        }
                        onClick={handleDownload}
                        disabled={
                          downloadKind !== null ||
                          completedDownloads.iso !== undefined ||
                          nativeHandoffIso
                        }
                        sx={browserHandoffContainedButtonSx(
                          nativeHandoffIso,
                          "success",
                        )}
                        className={
                          nativeHandoffIso ||
                          downloadKind !== null ||
                          completedDownloads.iso !== undefined
                            ? "cursor-default"
                            : "cursor-pointer"
                        }
                        aria-label={t("downloadZipAria")}
                        aria-describedby={
                          nativeHandoffIso
                            ? "burn-browser-handoff-help"
                            : undefined
                        }
                        aria-busy={downloadKind === "iso"}
                      >
                        {completedDownloads.iso !== undefined
                          ? t("downloadCompleted")
                          : downloadKind === "iso"
                            ? t("downloadInProgress")
                            : nativeHandoffIso
                              ? t("downloadSentToBrowserButton")
                              : t("downloadZip")}
                      </Button>
                    </>
                  ) : (
                    <>
                      <Box
                        sx={{
                          display: "flex",
                          flexDirection: "column",
                          gap: "10px",
                          width: "100%",
                        }}
                      >
                        <Paper
                          variant="outlined"
                          sx={{
                            p: 2,
                            display: "flex",
                            flexDirection: "column",
                            gap: 2,
                            borderColor: "success.light",
                          }}
                        >
                          <Box
                            sx={{
                              display: "flex",
                              alignItems: "flex-start",
                              gap: 1,
                            }}
                          >
                            <CheckCircleIcon
                              color="success"
                              fontSize="small"
                              sx={{ mt: 0.25, flexShrink: 0 }}
                              aria-hidden
                            />
                            <Typography variant="body2" color="text.secondary">
                              {t("ohifReady", { filename: buildJob.filename ?? "" })}
                            </Typography>
                          </Box>
                          <Button
                            variant="contained"
                            color="success"
                            size="large"
                            fullWidth
                            startIcon={
                              completedDownloads.iso !== undefined ? (
                                <CheckCircleIcon />
                              ) : nativeHandoffIso ? (
                                <CloudDownloadIcon />
                              ) : (
                                <DownloadIcon />
                              )
                            }
                            onClick={handleDownload}
                            disabled={
                              downloadKind !== null ||
                              completedDownloads.iso !== undefined ||
                              nativeHandoffIso
                            }
                            sx={browserHandoffContainedButtonSx(
                              nativeHandoffIso,
                              "success",
                            )}
                            className={
                              nativeHandoffIso ||
                              downloadKind !== null ||
                              completedDownloads.iso !== undefined
                                ? "cursor-default"
                                : "cursor-pointer"
                            }
                            aria-label={t("downloadIsoAria")}
                            aria-describedby={
                              nativeHandoffIso
                                ? "burn-browser-handoff-help"
                                : undefined
                            }
                            aria-busy={downloadKind === "iso"}
                          >
                            {completedDownloads.iso !== undefined
                              ? t("downloadCompleted")
                              : downloadKind === "iso"
                                ? t("downloadInProgress")
                                : nativeHandoffIso
                                  ? t("downloadSentToBrowserButton")
                                  : t("downloadIso")}
                          </Button>
                        </Paper>
                        {buildJob.kpacs_download_ready === true && (
                          <Paper
                            variant="outlined"
                            sx={{
                              p: 2,
                              display: "flex",
                              flexDirection: "column",
                              gap: 2,
                            }}
                          >
                            <Box
                              sx={{
                                display: "flex",
                                alignItems: "flex-start",
                                gap: 1,
                              }}
                            >
                              <CheckCircleIcon
                                color="primary"
                                fontSize="small"
                                sx={{ mt: 0.25, flexShrink: 0 }}
                                aria-hidden
                              />
                              <Typography variant="body2" color="text.secondary">
                                {buildJob.kpacs_filename
                                  ? t("kpacsReadyNamed", {
                                      filename: buildJob.kpacs_filename,
                                    })
                                  : t("kpacsReadyDefault")}
                              </Typography>
                            </Box>
                            <Button
                              variant="contained"
                              color="primary"
                              size="large"
                              fullWidth
                              startIcon={
                                completedDownloads.kpacs !== undefined ? (
                                  <CheckCircleIcon />
                                ) : nativeHandoffKpacs ? (
                                  <CloudDownloadIcon />
                                ) : (
                                  <DownloadIcon />
                                )
                              }
                              onClick={handleDownloadKpacs}
                              disabled={
                                downloadKind !== null ||
                                completedDownloads.kpacs !== undefined ||
                                nativeHandoffKpacs
                              }
                              sx={browserHandoffContainedButtonSx(
                                nativeHandoffKpacs,
                                "primary",
                              )}
                              className={
                                nativeHandoffKpacs ||
                                downloadKind !== null ||
                                completedDownloads.kpacs !== undefined
                                  ? "cursor-default"
                                  : "cursor-pointer"
                              }
                              aria-label={t("downloadKpacsAria")}
                              aria-describedby={
                                nativeHandoffKpacs
                                  ? "burn-browser-handoff-help"
                                  : undefined
                              }
                              aria-busy={downloadKind === "kpacs"}
                            >
                              {completedDownloads.kpacs !== undefined
                                ? t("downloadCompleted")
                                : downloadKind === "kpacs"
                                  ? t("downloadInProgress")
                                  : nativeHandoffKpacs
                                    ? t("downloadSentToBrowserButton")
                                    : t("downloadKpacs")}
                            </Button>
                          </Paper>
                        )}
                      </Box>
                      {buildJob.status === "complete" && buildJob.kpacs_error && (
                        <Alert severity="warning" className="mt-2" role="alert">
                          <Typography variant="body2" className="font-medium">
                            {t("kpacsUnavailableTitle")}
                          </Typography>
                          <Typography variant="body2" className="mt-1">
                            {buildJob.kpacs_error}
                          </Typography>
                        </Alert>
                      )}
                      <Typography
                        variant="body2"
                        className="mt-3 block text-center text-gray-700 font-medium"
                      >
                        {t("burnHint")}
                      </Typography>
                    </>
                  )}
                </>
              )}
            </Box>
          )}
        </DialogContent>
        <DialogActions>
          <Button
            onClick={handleClose}
            disabled={
              downloadKind !== null ||
              (buildJob !== null &&
                buildJob.status !== "complete" &&
                buildJob.status !== "error")
            }
          >
            {t("close")}
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default BurnPanel;

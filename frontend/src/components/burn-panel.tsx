"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
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
} from "@mui/material";
import AlbumIcon from "@mui/icons-material/Album";
import DownloadIcon from "@mui/icons-material/Download";
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
import { modalitiesTokens } from "@/lib/modality-utils";

const selectionIncludesNM = (
  studies: { study_instance_uid: string; modalities_in_study: string | null }[],
  selectedStudies: string[],
  seriesMap: Record<string, { series_instance_uid: string; modality: string }[]>,
  selectedSeries: string[]
): boolean => {
  if (selectedSeries.length > 0) {
    for (const studyUid of selectedStudies) {
      for (const ser of seriesMap[studyUid] ?? []) {
        if (!selectedSeries.includes(ser.series_instance_uid)) continue;
        if ((ser.modality ?? "").toUpperCase().trim() === "NM") return true;
      }
    }
    return false;
  }
  for (const uid of selectedStudies) {
    const study = studies.find((s) => s.study_instance_uid === uid);
    if (study && modalitiesTokens(study.modalities_in_study).includes("NM")) return true;
  }
  return false;
};

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
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const firstSelectedStudy = studies.find((s) =>
    selectedStudies.includes(s.study_instance_uid)
  );
  const burnPatientId =
    selectedPatient?.patient_id ?? firstSelectedStudy?.patient_id ?? "";
  const burnPatientName =
    selectedPatient?.patient_name ?? firstSelectedStudy?.patient_name ?? "";
  const expectedInstances = selectedStudies.reduce((sum, studyUid) => {
    const study = studies.find((s) => s.study_instance_uid === studyUid);
    return sum + (study?.number_of_instances ?? 0);
  }, 0);

  const hideOhifIsoDownload = useMemo(
    () => selectionIncludesNM(studies, selectedStudies, seriesMap, selectedSeries),
    [studies, selectedStudies, seriesMap, selectedSeries]
  );

  const canBuild =
    Boolean(selectedNode) &&
    selectedStudies.length > 0 &&
    Boolean(burnPatientId);

  const startBuild = useCallback(
    async (opts: { studyZipOnly: boolean }) => {
      if (!selectedNode || !burnPatientId) return;

      setError(null);
      setDialogOpen(true);

      try {
        const { job_id } = await createCd({
          node_ae_title: selectedNode.ae_title,
          patient_id: burnPatientId,
          patient_name: burnPatientName || t("patientFallback"),
          studies: selectedStudies,
          series: selectedSeries.length > 0 ? selectedSeries : undefined,
          expected_instances: expectedInstances > 0 ? expectedInstances : undefined,
          include_viewer: true,
          include_kpacs: !opts.studyZipOnly,
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
          expected_instances: expectedInstances > 0 ? expectedInstances : null,
        });

        pollRef.current = setInterval(async () => {
          try {
            const status = await getBuildStatus(job_id);
            setBuildJob(status);
            if (status.status === "complete" || status.status === "error") {
              if (pollRef.current) clearInterval(pollRef.current);
            }
          } catch {
            if (pollRef.current) clearInterval(pollRef.current);
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
      setBuildJob,
      t,
    ]
  );

  const handleDownload = useCallback(() => {
    if (!buildJob?.job_id) return;
    window.open(getDownloadUrl(buildJob.job_id), "_blank");
  }, [buildJob]);

  const handleDownloadKpacs = useCallback(() => {
    if (!buildJob?.job_id) return;
    window.open(getKpacsDownloadUrl(buildJob.job_id), "_blank");
  }, [buildJob]);

  const handleClose = useCallback(async () => {
    if (buildJob?.job_id) {
      try {
        await cleanupJob(buildJob.job_id);
      } catch {
        // server cleanup is best-effort
      }
    }
    setDialogOpen(false);
    setBuildJob(null);
  }, [buildJob, setBuildJob]);

  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, []);

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
      <Paper className="p-4">
        <Typography variant="h6" className="mb-3 flex items-center gap-2">
          <AlbumIcon /> {t("title")}
        </Typography>

        <Box className="flex items-center gap-3 flex-wrap">
          <Typography variant="body2" className="text-gray-600">
            {t("studiesSelected", { count: selectedStudies.length })}
          </Typography>

          <Button
            variant="contained"
            color="secondary"
            startIcon={<FolderZipIcon />}
            onClick={() => {
              startBuild({ studyZipOnly: true }).catch(console.error);
            }}
            disabled={!canBuild}
            className="cursor-pointer"
            aria-label={t("downloadStudyZipAria")}
          >
            {t("downloadStudyZip")}
          </Button>

          <Button
            variant="contained"
            color="primary"
            startIcon={<LocalFireDepartmentIcon />}
            onClick={() => {
              startBuild({ studyZipOnly: false }).catch(console.error);
            }}
            disabled={!canBuild}
            className="cursor-pointer"
            aria-label={t("buildIsoAria")}
          >
            {t("buildIso")}
          </Button>

          <Typography variant="caption" className="text-gray-500 max-w-xl block">
            {t("hintZip")}
          </Typography>
        </Box>

        {error && (
          <Alert severity="error" className="mt-3" role="alert">
            {error}
          </Alert>
        )}
      </Paper>

      <Dialog
        open={dialogOpen}
        onClose={() => {
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

              <LinearProgress
                variant="determinate"
                value={buildJob.progress * 100}
                className="rounded"
                aria-label={t("progressAria")}
                aria-valuenow={buildJob.progress * 100}
                aria-valuemin={0}
                aria-valuemax={100}
              />

              <Typography variant="body2" className="text-gray-600">
                {buildJob.message}
              </Typography>
              <Typography variant="body2" className="text-gray-700 font-medium">
                {t("retrievedInstances", {
                  count: buildJob.retrieved_instances,
                })}
              </Typography>

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
                        startIcon={<DownloadIcon />}
                        onClick={handleDownload}
                        className="cursor-pointer"
                        aria-label={t("downloadZipAria")}
                      >
                        {t("downloadZip")}
                      </Button>
                    </>
                  ) : (
                    <>
                      {hideOhifIsoDownload ? (
                        <Alert severity="info" role="status">
                          <Typography variant="body2" className="font-medium">
                            {t("nmTitle")}
                          </Typography>
                          <Typography variant="body2" className="mt-1">
                            {t("nmBody")}
                          </Typography>
                        </Alert>
                      ) : (
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
                              startIcon={<DownloadIcon />}
                              onClick={handleDownload}
                              className="cursor-pointer"
                              aria-label={t("downloadIsoAria")}
                            >
                              {t("downloadIso")}
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
                                startIcon={<DownloadIcon />}
                                onClick={handleDownloadKpacs}
                                className="cursor-pointer"
                                aria-label={t("downloadKpacsAria")}
                              >
                                {t("downloadKpacs")}
                              </Button>
                            </Paper>
                          )}
                        </Box>
                      )}
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
                      {hideOhifIsoDownload && buildJob.kpacs_download_ready && (
                        <Paper
                          variant="outlined"
                          sx={{
                            mt: "10px",
                            p: 2,
                            display: "flex",
                            flexDirection: "column",
                            gap: 2,
                            width: "100%",
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
                            className="cursor-pointer"
                            startIcon={<DownloadIcon />}
                            onClick={handleDownloadKpacs}
                            aria-label={t("downloadKpacsAria")}
                          >
                            {t("downloadKpacs")}
                          </Button>
                        </Paper>
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
              buildJob !== null &&
              buildJob.status !== "complete" &&
              buildJob.status !== "error"
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

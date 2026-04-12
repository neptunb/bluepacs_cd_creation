"use client";

import { useState, useEffect, useRef, useCallback, useMemo } from "react";
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

const BurnPanel = () => {
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
          patient_name: burnPatientName || "Patient",
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
          message: "Job queued...",
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
          opts.studyZipOnly
            ? "Failed to start STUDY download. Check server connection."
            : "Failed to create CD image. Check server connection."
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
          <AlbumIcon /> Create CD Image
        </Typography>

        <Box className="flex items-center gap-3 flex-wrap">
          <Typography variant="body2" className="text-gray-600">
            {selectedStudies.length} {selectedStudies.length === 1 ? "study" : "studies"} selected
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
            aria-label="Download selected studies as STUDY folder ZIP"
          >
            Download STUDY (ZIP)
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
            aria-label="Build CD image for download"
          >
            Build ISO
          </Button>

          <Typography variant="caption" className="text-gray-500 max-w-xl block">
            Download STUDY (ZIP) delivers only a <code className="text-xs">.zip</code> with paths like{" "}
            <code className="text-xs">STUDY/&lt;study-uid&gt;/…</code>. Build ISO puts images under{" "}
            <code className="text-xs">DICOM/</code> on the disc — there is no{" "}
            <code className="text-xs">STUDY/</code> folder inside the OHIF ISO. K-PACS ISO is separate.
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
            ? "STUDY folder (ZIP)"
            : "CD Image Builder"}
        </DialogTitle>
        <DialogContent>
          {buildJob && (
            <Box className="space-y-4 py-2">
              <Box className="flex items-center gap-2">
                <Typography variant="body2">Status:</Typography>
                <Chip
                  label={buildJob.status}
                  color={statusColor(buildJob.status)}
                  size="small"
                  icon={getStatusIcon(buildJob.status)}
                />
              </Box>

              <LinearProgress
                variant="determinate"
                value={buildJob.progress * 100}
                className="rounded"
                aria-label="Build progress"
                aria-valuenow={buildJob.progress * 100}
                aria-valuemin={0}
                aria-valuemax={100}
              />

              <Typography variant="body2" className="text-gray-600">
                {buildJob.message}
              </Typography>
              <Typography variant="body2" className="text-gray-700 font-medium">
                Retrieved instances: {buildJob.retrieved_instances}
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
                        ZIP contains a <code className="text-xs">STUDY/</code> tree with the same
                        instances that were retrieved from the PACS (one folder per study UID).
                      </Alert>
                      <Button
                        variant="contained"
                        color="success"
                        size="large"
                        fullWidth
                        startIcon={<DownloadIcon />}
                        onClick={handleDownload}
                        className="cursor-pointer"
                        aria-label="Download STUDY folder ZIP file"
                      >
                        Download ZIP to My PC
                      </Button>
                    </>
                  ) : (
                    <>
                      {hideOhifIsoDownload ? (
                        <Alert severity="info" role="status">
                          <Typography variant="body2" className="font-medium">
                            Nuclear Medicine (NM) in this selection
                          </Typography>
                          <Typography variant="body2" className="mt-1">
                            The on-disc OHIF viewer is not offered for NM. Use{" "}
                            <strong>Download K-PACS to My PC</strong> or{" "}
                            <strong>Download STUDY (ZIP)</strong> for other viewers (e.g. Horos).
                          </Typography>
                        </Alert>
                      ) : (
                        <>
                          <Alert severity="success" icon={<CheckCircleIcon />}>
                            <Typography variant="body2" className="font-medium">
                              {buildJob.filename}
                            </Typography>
                            OHIF viewer ISO is ready. Download it and burn to CD/DVD on your PC.
                          </Alert>
                          <Button
                            variant="contained"
                            color="success"
                            size="large"
                            fullWidth
                            startIcon={<DownloadIcon />}
                            onClick={handleDownload}
                            className="cursor-pointer"
                            aria-label="Download ISO file"
                          >
                            Download ISO to My PC
                          </Button>
                        </>
                      )}
                      {buildJob.status === "complete" && buildJob.kpacs_error && (
                        <Alert severity="warning" className="mt-2" role="alert">
                          <Typography variant="body2" className="font-medium">
                            K-PACS ISO not available
                          </Typography>
                          <Typography variant="body2" className="mt-1">
                            {buildJob.kpacs_error}
                          </Typography>
                        </Alert>
                      )}
                      {buildJob.kpacs_download_ready && (
                        <Button
                          variant="contained"
                          color="primary"
                          size="large"
                          fullWidth
                          className="mt-3 cursor-pointer"
                          startIcon={<DownloadIcon />}
                          onClick={handleDownloadKpacs}
                          aria-label="Download K-PACS disc ISO file"
                        >
                          Download K-PACS to My PC
                        </Button>
                      )}
                      {buildJob.kpacs_download_ready && buildJob.kpacs_filename && (
                        <Typography variant="caption" className="mt-1 block text-center text-gray-600">
                          {buildJob.kpacs_filename} — K-PACS Lite layout with DICOMDIR (Windows viewer
                          on disc)
                        </Typography>
                      )}
                      <Typography
                        variant="body2"
                        className="mt-3 block text-center text-gray-700 font-medium"
                      >
                        After downloading, right-click the .iso file and select
                        &quot;Burn disc image&quot; (Windows) or use Disk Utility (macOS)
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
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </>
  );
};

export default BurnPanel;

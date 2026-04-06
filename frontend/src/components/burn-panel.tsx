"use client";

import { useState, useEffect, useRef, useCallback } from "react";
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
import { useCdStore } from "@/store/use-cd-store";
import { createCd, getBuildStatus, getDownloadUrl, cleanupJob } from "@/lib/api";

const BurnPanel = () => {
  const {
    selectedNode,
    selectedPatient,
    studies,
    selectedStudies,
    selectedSeries,
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

  const canBuild =
    Boolean(selectedNode) &&
    selectedStudies.length > 0 &&
    Boolean(burnPatientId);

  const startBuild = useCallback(async () => {
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
        include_viewer: true,
      });

      setBuildJob({
        job_id,
        status: "queued",
        progress: 0,
        message: "Job queued...",
        filename: null,
        download_ready: false,
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
      setError("Failed to create CD image. Check server connection.");
    }
  }, [
    selectedNode,
    burnPatientId,
    burnPatientName,
    selectedStudies,
    selectedSeries,
    setBuildJob,
  ]);

  const handleDownload = useCallback(() => {
    if (!buildJob?.job_id) return;
    window.open(getDownloadUrl(buildJob.job_id), "_blank");
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
            color="primary"
            startIcon={<LocalFireDepartmentIcon />}
            onClick={startBuild}
            disabled={!canBuild}
            className="cursor-pointer"
            aria-label="Build CD image for download"
          >
            Build ISO
          </Button>

          <Typography variant="caption" className="text-gray-400">
            The ISO will be downloaded to your PC for local burning
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
          CD Image Builder
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
                  icon={
                    buildJob.status === "complete" ? (
                      <CheckCircleIcon />
                    ) : buildJob.status === "error" ? (
                      <ErrorIcon />
                    ) : undefined
                  }
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

              {buildJob.download_ready && (
                <>
                  <Divider />
                  <Alert severity="success" icon={<CheckCircleIcon />}>
                    <Typography variant="body2" className="font-medium">
                      {buildJob.filename}
                    </Typography>
                    ISO is ready. Download it and burn to CD/DVD on your PC.
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
                  <Typography variant="caption" className="text-gray-400 block text-center">
                    After downloading, right-click the .iso file and select
                    &quot;Burn disc image&quot; (Windows) or use Disk Utility (macOS)
                  </Typography>
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

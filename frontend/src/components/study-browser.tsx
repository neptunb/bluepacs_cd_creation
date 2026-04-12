"use client";

import { Fragment, useEffect, useCallback, useState } from "react";
import {
  Paper,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Checkbox,
  Button,
  Box,
  Chip,
  CircularProgress,
  Collapse,
  IconButton,
  Alert,
} from "@mui/material";
import FolderIcon from "@mui/icons-material/Folder";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import ExpandLessIcon from "@mui/icons-material/ExpandLess";
import SelectAllIcon from "@mui/icons-material/SelectAll";
import DeselectIcon from "@mui/icons-material/Deselect";
import { useCdStore } from "@/store/use-cd-store";
import { fetchStudies, fetchSeries } from "@/lib/api";
import { formatModalitiesLabel } from "@/lib/modality-utils";
import type { Series } from "@/lib/types";

const StudyBrowser = () => {
  const {
    selectedNode,
    selectedPatient,
    latestStudiesMode,
    studies,
    selectedStudies,
    studiesLoading,
    seriesMap,
    setStudies,
    toggleStudySelection,
    selectAllStudies,
    clearStudySelection,
    setStudiesLoading,
    setSeriesForStudy,
  } = useCdStore();

  const [expandedStudy, setExpandedStudy] = useState<string | null>(null);
  const [seriesLoading, setSeriesLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (latestStudiesMode || !selectedPatient || !selectedNode) return;

    const loadStudies = async () => {
      setStudiesLoading(true);
      setError(null);
      try {
        const results = await fetchStudies(
          selectedPatient.patient_id,
          selectedNode.ae_title
        );
        setStudies(results);
      } catch (err) {
        console.error("Failed to fetch studies:", err);
        setError("Failed to load studies.");
      } finally {
        setStudiesLoading(false);
      }
    };

    loadStudies();
  }, [
    latestStudiesMode,
    selectedPatient,
    selectedNode,
    setStudies,
    setStudiesLoading,
  ]);

  const handleExpandStudy = useCallback(
    async (studyUid: string) => {
      if (expandedStudy === studyUid) {
        setExpandedStudy(null);
        return;
      }

      setExpandedStudy(studyUid);

      if (!seriesMap[studyUid] && selectedNode) {
        setSeriesLoading(true);
        try {
          const series = await fetchSeries(studyUid, selectedNode.ae_title);
          setSeriesForStudy(studyUid, series);
        } catch (err) {
          console.error("Failed to fetch series:", err);
        } finally {
          setSeriesLoading(false);
        }
      }
    },
    [expandedStudy, seriesMap, selectedNode, setSeriesForStudy]
  );

  if (!selectedNode || (!selectedPatient && !latestStudiesMode)) return null;

  return (
    <Paper className="p-4">
      <Box className="flex items-center justify-between mb-3">
        <Typography variant="h6" className="flex items-center gap-2">
          <FolderIcon />
          {latestStudiesMode
            ? `Latest studies — ${selectedNode.name || selectedNode.ae_title}`
            : `Studies for ${selectedPatient?.patient_name ?? ""}`}
        </Typography>
        <Box className="flex gap-2">
          <Button
            size="small"
            startIcon={<SelectAllIcon />}
            onClick={selectAllStudies}
            disabled={studies.length === 0}
            className="cursor-pointer"
            aria-label="Select all studies"
          >
            Select All
          </Button>
          <Button
            size="small"
            startIcon={<DeselectIcon />}
            onClick={clearStudySelection}
            disabled={selectedStudies.length === 0}
            className="cursor-pointer"
            aria-label="Deselect all studies"
          >
            Deselect
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" className="mb-3" role="alert">
          {error}
        </Alert>
      )}

      {studiesLoading ? (
        <Box className="flex justify-center py-8">
          <CircularProgress aria-label="Loading studies" />
        </Box>
      ) : (
        <TableContainer>
          <Table size="small" aria-label="Study list">
            <TableHead>
              <TableRow className="bg-gray-100">
                <TableCell padding="checkbox" />
                <TableCell />
                {latestStudiesMode && <TableCell>Patient ID</TableCell>}
                {latestStudiesMode && <TableCell>Patient name</TableCell>}
                <TableCell>Date</TableCell>
                <TableCell>Description</TableCell>
                <TableCell>Modality</TableCell>
                <TableCell align="center">Series</TableCell>
                <TableCell align="center">Images</TableCell>
                <TableCell>Accession</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {studies.map((study) => (
                <Fragment key={study.study_instance_uid}>
                  <TableRow
                    hover
                    className="cursor-pointer hover:bg-blue-50 transition-colors"
                  >
                    <TableCell padding="checkbox">
                      <Checkbox
                        checked={selectedStudies.includes(study.study_instance_uid)}
                        onChange={() => toggleStudySelection(study.study_instance_uid)}
                        aria-label={`Select study ${study.study_description || study.study_instance_uid}`}
                      />
                    </TableCell>
                    <TableCell>
                      <IconButton
                        size="small"
                        onClick={() => handleExpandStudy(study.study_instance_uid)}
                        aria-expanded={expandedStudy === study.study_instance_uid}
                        aria-label="Expand series"
                      >
                        {expandedStudy === study.study_instance_uid ? (
                          <ExpandLessIcon />
                        ) : (
                          <ExpandMoreIcon />
                        )}
                      </IconButton>
                    </TableCell>
                    {latestStudiesMode && (
                      <TableCell>{study.patient_id || "—"}</TableCell>
                    )}
                    {latestStudiesMode && (
                      <TableCell>{study.patient_name || "—"}</TableCell>
                    )}
                    <TableCell>{study.study_date || "—"}</TableCell>
                    <TableCell className="font-medium">
                      {study.study_description || "No description"}
                    </TableCell>
                    <TableCell>
                      <Chip
                        label={formatModalitiesLabel(study.modalities_in_study)}
                        size="small"
                        color="primary"
                        variant="outlined"
                      />
                    </TableCell>
                    <TableCell align="center">{study.number_of_series ?? "—"}</TableCell>
                    <TableCell align="center">{study.number_of_instances ?? "—"}</TableCell>
                    <TableCell>{study.accession_number || "—"}</TableCell>
                  </TableRow>

                  <TableRow>
                    <TableCell
                      colSpan={latestStudiesMode ? 10 : 8}
                      className="p-0 border-0"
                    >
                      <Collapse
                        in={expandedStudy === study.study_instance_uid}
                        timeout="auto"
                        unmountOnExit
                      >
                        <SeriesDetail
                          studyUid={study.study_instance_uid}
                          series={seriesMap[study.study_instance_uid] || []}
                          loading={seriesLoading && expandedStudy === study.study_instance_uid}
                        />
                      </Collapse>
                    </TableCell>
                  </TableRow>
                </Fragment>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {!studiesLoading && studies.length === 0 && (
        <Typography variant="body2" className="text-gray-500 text-center py-4">
          {latestStudiesMode
            ? "No studies returned. The archive may be empty or the query timed out."
            : "No studies found for this patient."}
        </Typography>
      )}
    </Paper>
  );
};

const SeriesDetail = ({
  studyUid,
  series,
  loading,
}: {
  studyUid: string;
  series: Series[];
  loading: boolean;
}) => {
  if (loading) {
    return (
      <Box className="flex justify-center py-4">
        <CircularProgress size={24} aria-label="Loading series" />
      </Box>
    );
  }

  return (
    <Box className="pl-12 pr-4 py-2 bg-gray-50">
      <Typography variant="subtitle2" className="mb-2 text-gray-600">
        Series in study
      </Typography>
      <Table size="small" aria-label={`Series for study ${studyUid}`}>
        <TableHead>
          <TableRow>
            <TableCell>#</TableCell>
            <TableCell>Description</TableCell>
            <TableCell>Modality</TableCell>
            <TableCell align="center">Images</TableCell>
            <TableCell>Body Part</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {series.map((s) => (
            <TableRow key={s.series_instance_uid} hover>
              <TableCell>{s.series_number ?? "—"}</TableCell>
              <TableCell>{s.series_description || "No description"}</TableCell>
              <TableCell>
                <Chip label={s.modality} size="small" variant="outlined" />
              </TableCell>
              <TableCell align="center">{s.number_of_instances ?? "—"}</TableCell>
              <TableCell>{s.body_part_examined || "—"}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Box>
  );
};

export default StudyBrowser;

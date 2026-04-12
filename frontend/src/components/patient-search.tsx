"use client";

import { useState, useCallback, useEffect } from "react";
import type { KeyboardEvent, SyntheticEvent } from "react";
import {
  TextField,
  Button,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Typography,
  Box,
  CircularProgress,
  Alert,
  ToggleButton,
  ToggleButtonGroup,
} from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import PersonIcon from "@mui/icons-material/Person";
import DateRangeIcon from "@mui/icons-material/DateRange";
import { useCdStore } from "@/store/use-cd-store";
import { searchPatients } from "@/lib/api";

type SearchMode = "name_id" | "study_date";

const toDicomStudyDate = (htmlDate: string): string => htmlDate.replace(/-/g, "");

const PatientSearch = () => {
  const {
    selectedNode,
    patients,
    selectedPatient,
    patientSearchLoading,
    setPatients,
    setSelectedPatient,
    setPatientSearchLoading,
  } = useCdStore();

  const [searchMode, setSearchMode] = useState<SearchMode>("name_id");
  const [nameQuery, setNameQuery] = useState("");
  const [idQuery, setIdQuery] = useState("");
  const [studyDateFrom, setStudyDateFrom] = useState("");
  const [studyDateTo, setStudyDateTo] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setPatients([]);
    setSelectedPatient(null);
    setError(null);
  }, [searchMode, setPatients, setSelectedPatient]);

  const handleSearch = useCallback(async () => {
    if (!selectedNode) return;

    if (searchMode === "name_id") {
      if (!nameQuery && !idQuery) return;
    } else {
      if (!studyDateFrom || !studyDateTo) return;
      const a = toDicomStudyDate(studyDateFrom);
      const b = toDicomStudyDate(studyDateTo);
      if (a > b) {
        setError("Start date must be on or before end date.");
        return;
      }
    }

    setPatientSearchLoading(true);
    setError(null);

    try {
      const results =
        searchMode === "name_id"
          ? await searchPatients({
              node_ae_title: selectedNode.ae_title,
              patient_name: nameQuery || undefined,
              patient_id: idQuery || undefined,
            })
          : await searchPatients({
              node_ae_title: selectedNode.ae_title,
              study_date_from: toDicomStudyDate(studyDateFrom),
              study_date_to: toDicomStudyDate(studyDateTo),
            });
      setPatients(results);
    } catch (err) {
      console.error("Patient search failed:", err);
      setError("Failed to search patients. Check DICOM node connection.");
    } finally {
      setPatientSearchLoading(false);
    }
  }, [
    selectedNode,
    searchMode,
    nameQuery,
    idQuery,
    studyDateFrom,
    studyDateTo,
    setPatients,
    setPatientSearchLoading,
  ]);

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === "Enter") handleSearch();
  };

  return (
    <Paper className="p-4">
      <Typography variant="h6" className="mb-3 flex items-center gap-2">
        <PersonIcon /> Patient Search
      </Typography>

      <ToggleButtonGroup
        value={searchMode}
        exclusive
        onChange={(_event: SyntheticEvent, value: SearchMode | null) => {
          if (value) setSearchMode(value);
        }}
        size="small"
        className="mb-4"
        aria-label="Patient search mode"
      >
        <ToggleButton value="name_id" className="cursor-pointer normal-case" aria-label="Search by name or ID">
          Name / ID
        </ToggleButton>
        <ToggleButton value="study_date" className="cursor-pointer normal-case" aria-label="Search by study date range">
          <DateRangeIcon fontSize="small" className="mr-1" aria-hidden />
          Study dates
        </ToggleButton>
      </ToggleButtonGroup>

      <Box className="flex gap-3 mb-4 flex-wrap items-end">
        {searchMode === "name_id" ? (
          <>
            <TextField
              label="Patient Name"
              size="small"
              value={nameQuery}
              onChange={(e) => setNameQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="e.g. Smith or John (partial name)"
              className="flex-1 min-w-[200px]"
              aria-label="Search by patient name"
            />
            <TextField
              label="Patient ID"
              size="small"
              value={idQuery}
              onChange={(e) => setIdQuery(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="e.g. 12345"
              className="flex-1 min-w-[150px]"
              aria-label="Search by patient ID"
            />
          </>
        ) : (
          <>
            <TextField
              label="Study date from"
              type="date"
              size="small"
              value={studyDateFrom}
              onChange={(e) => setStudyDateFrom(e.target.value)}
              onKeyDown={handleKeyDown}
              InputLabelProps={{ shrink: true }}
              className="min-w-[180px]"
              aria-label="Study date range start"
            />
            <TextField
              label="Study date to"
              type="date"
              size="small"
              value={studyDateTo}
              onChange={(e) => setStudyDateTo(e.target.value)}
              onKeyDown={handleKeyDown}
              InputLabelProps={{ shrink: true }}
              className="min-w-[180px]"
              aria-label="Study date range end"
            />
          </>
        )}
        <Button
          variant="contained"
          startIcon={patientSearchLoading ? <CircularProgress size={18} color="inherit" /> : <SearchIcon />}
          onClick={handleSearch}
          disabled={
            !selectedNode ||
            patientSearchLoading ||
            (searchMode === "name_id" ? !nameQuery && !idQuery : !studyDateFrom || !studyDateTo)
          }
          className="cursor-pointer"
          aria-label="Search patients"
        >
          Search
        </Button>
      </Box>

      {error && (
        <Alert severity="error" className="mb-3" role="alert">
          {error}
        </Alert>
      )}

      {patients.length > 0 && (
        <TableContainer>
          <Table size="small" aria-label="Patient search results">
            <TableHead>
              <TableRow className="bg-gray-100">
                <TableCell>Patient ID</TableCell>
                <TableCell>Patient Name</TableCell>
                <TableCell>Birth Date</TableCell>
                <TableCell>Sex</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {patients.map((patient) => (
                <TableRow
                  key={patient.patient_id}
                  hover
                  selected={selectedPatient?.patient_id === patient.patient_id}
                  onClick={() => setSelectedPatient(patient)}
                  className="cursor-pointer hover:bg-blue-50 transition-colors"
                  role="button"
                  tabIndex={0}
                  aria-selected={selectedPatient?.patient_id === patient.patient_id}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") setSelectedPatient(patient);
                  }}
                >
                  <TableCell>{patient.patient_id}</TableCell>
                  <TableCell className="font-medium">{patient.patient_name}</TableCell>
                  <TableCell>{patient.birth_date || "—"}</TableCell>
                  <TableCell>{patient.sex || "—"}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      {!patientSearchLoading &&
        patients.length === 0 &&
        (searchMode === "name_id" ? nameQuery || idQuery : studyDateFrom && studyDateTo) && (
          <Typography variant="body2" className="text-gray-500 text-center py-4">
            No patients found. Try a different search.
          </Typography>
        )}
    </Paper>
  );
};

export default PatientSearch;

"use client";

import { useState, useCallback } from "react";
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
} from "@mui/material";
import SearchIcon from "@mui/icons-material/Search";
import PersonIcon from "@mui/icons-material/Person";
import { useCdStore } from "@/store/use-cd-store";
import { searchPatients } from "@/lib/api";

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

  const [nameQuery, setNameQuery] = useState("");
  const [idQuery, setIdQuery] = useState("");
  const [error, setError] = useState<string | null>(null);

  const handleSearch = useCallback(async () => {
    if (!selectedNode) return;
    if (!nameQuery && !idQuery) return;

    setPatientSearchLoading(true);
    setError(null);

    try {
      const results = await searchPatients({
        node_ae_title: selectedNode.ae_title,
        patient_name: nameQuery || undefined,
        patient_id: idQuery || undefined,
      });
      setPatients(results);
    } catch (err) {
      console.error("Patient search failed:", err);
      setError("Failed to search patients. Check DICOM node connection.");
    } finally {
      setPatientSearchLoading(false);
    }
  }, [selectedNode, nameQuery, idQuery, setPatients, setPatientSearchLoading]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") handleSearch();
  };

  return (
    <Paper className="p-4">
      <Typography variant="h6" className="mb-3 flex items-center gap-2">
        <PersonIcon /> Patient Search
      </Typography>

      <Box className="flex gap-3 mb-4 flex-wrap">
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
        <Button
          variant="contained"
          startIcon={patientSearchLoading ? <CircularProgress size={18} color="inherit" /> : <SearchIcon />}
          onClick={handleSearch}
          disabled={!selectedNode || patientSearchLoading || (!nameQuery && !idQuery)}
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

      {!patientSearchLoading && patients.length === 0 && (nameQuery || idQuery) && (
        <Typography variant="body2" className="text-gray-500 text-center py-4">
          No patients found. Try a different search.
        </Typography>
      )}
    </Paper>
  );
};

export default PatientSearch;

"use client";

import { useEffect, useState } from "react";
import {
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  Box,
  IconButton,
  Tooltip,
  CircularProgress,
  Alert,
  Button,
  Typography,
} from "@mui/material";
import WifiIcon from "@mui/icons-material/Wifi";
import WifiOffIcon from "@mui/icons-material/WifiOff";
import HistoryIcon from "@mui/icons-material/History";
import { useCdStore } from "@/store/use-cd-store";
import { fetchNodes, echoNode, fetchRecentStudies } from "@/lib/api";
import type { SelectChangeEvent } from "@mui/material";

const NodeSelector = () => {
  const {
    nodes,
    selectedNode,
    setNodes,
    setSelectedNode,
    loadLatestStudies,
    setStudiesLoading,
  } = useCdStore();
  const [echoStatus, setEchoStatus] = useState<Record<string, boolean | null>>({});
  const [echoLoading, setEchoLoading] = useState<string | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadDone, setLoadDone] = useState(false);
  const [recentLoading, setRecentLoading] = useState(false);
  const [recentError, setRecentError] = useState<string | null>(null);

  useEffect(() => {
    const loadNodes = async () => {
      setLoadError(null);
      setLoadDone(false);
      try {
        const data = await fetchNodes();
        setNodes(data);
        if (data.length > 0) {
          setSelectedNode(data[0]);
        } else {
          setLoadError(
            "No DICOM nodes returned. Check backend/dicom_nodes.json and rebuild if needed."
          );
        }
      } catch (err) {
        console.error("Failed to fetch nodes:", err);
        setLoadError(
          "Could not load DICOM nodes from the API. If you use Docker, rebuild the frontend image so the API proxy points at the backend container."
        );
      } finally {
        setLoadDone(true);
      }
    };
    loadNodes();
  }, [setNodes, setSelectedNode]);

  const handleChange = (event: SelectChangeEvent) => {
    const node = nodes.find((n) => n.ae_title === event.target.value);
    setSelectedNode(node || null);
  };

  const handleLatestStudies = async () => {
    if (!selectedNode) return;
    setRecentError(null);
    setRecentLoading(true);
    setStudiesLoading(true);
    try {
      const data = await fetchRecentStudies({
        node_ae_title: selectedNode.ae_title,
        limit: 10,
      });
      loadLatestStudies(data);
    } catch (err) {
      console.error("Recent studies failed:", err);
      setRecentError("Could not load the latest studies for this node.");
    } finally {
      setRecentLoading(false);
      setStudiesLoading(false);
    }
  };

  const handleEcho = async () => {
    if (!selectedNode) return;
    setEchoLoading(selectedNode.ae_title);
    try {
      const reachable = await echoNode(selectedNode.ae_title);
      setEchoStatus((prev) => ({ ...prev, [selectedNode.ae_title]: reachable }));
    } catch {
      setEchoStatus((prev) => ({ ...prev, [selectedNode.ae_title]: false }));
    } finally {
      setEchoLoading(null);
    }
  };

  return (
    <Box className="flex flex-col gap-2">
      {loadError && (
        <Alert severity="error" role="alert">
          {loadError}
        </Alert>
      )}
      {!loadDone && !loadError && (
        <Box className="flex items-center gap-2 text-gray-600 text-sm">
          <CircularProgress size={16} />
          Loading DICOM nodes…
        </Box>
      )}
      <Box className="flex items-center gap-3 flex-wrap">
      <FormControl size="small" className="min-w-[200px]">
        <InputLabel id="node-select-label">DICOM Node</InputLabel>
        <Select
          labelId="node-select-label"
          value={selectedNode?.ae_title || ""}
          label="DICOM Node"
          onChange={handleChange}
          aria-label="Select DICOM node"
        >
          {nodes.map((node) => (
            <MenuItem key={node.ae_title} value={node.ae_title}>
              {node.name || node.ae_title} ({node.ae_title})
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      <Tooltip title="Test connection (C-ECHO)">
        <span>
          <IconButton
            onClick={handleEcho}
            disabled={!selectedNode || echoLoading !== null}
            aria-label="Test DICOM node connection"
            className="cursor-pointer hover:scale-110 transition-transform"
          >
            {echoLoading ? (
              <CircularProgress size={20} />
            ) : echoStatus[selectedNode?.ae_title || ""] === true ? (
              <WifiIcon color="success" />
            ) : echoStatus[selectedNode?.ae_title || ""] === false ? (
              <WifiOffIcon color="error" />
            ) : (
              <WifiIcon color="action" />
            )}
          </IconButton>
        </span>
      </Tooltip>

      {selectedNode && echoStatus[selectedNode.ae_title] !== undefined && (
        <Chip
          label={echoStatus[selectedNode.ae_title] ? "Connected" : "Unreachable"}
          color={echoStatus[selectedNode.ae_title] ? "success" : "error"}
          size="small"
          variant="outlined"
        />
      )}

      <Button
        variant="outlined"
        size="small"
        startIcon={
          recentLoading ? (
            <CircularProgress color="inherit" size={16} />
          ) : (
            <HistoryIcon />
          )
        }
        onClick={handleLatestStudies}
        disabled={!selectedNode || recentLoading}
        className="cursor-pointer"
        aria-label="Load latest 10 studies from selected node"
      >
        Latest 10 studies
      </Button>
      </Box>

      {recentError && (
        <Typography variant="body2" className="text-red-600" role="alert">
          {recentError}
        </Typography>
      )}
    </Box>
  );
};

export default NodeSelector;

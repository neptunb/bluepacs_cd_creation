"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
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
import { readLastSelectedDicomNodeAe } from "@/lib/persisted-dicom-node";
import { format, subDays } from "date-fns";
import { fetchNodes, echoNode, fetchRecentStudies } from "@/lib/api";
import type { SelectChangeEvent } from "@mui/material";

const NodeSelector = () => {
  const t = useTranslations("nodeSelector");
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
          const savedAe = readLastSelectedDicomNodeAe();
          const fromStorage = savedAe
            ? data.find((n) => n.ae_title === savedAe)
            : undefined;
          setSelectedNode(fromStorage ?? data[0]);
        } else {
          setSelectedNode(null);
          setLoadError(t("errorNoNodes"));
        }
      } catch (err) {
        console.error("Failed to fetch nodes:", err);
        setLoadError(t("errorLoadNodes"));
      } finally {
        setLoadDone(true);
      }
    };
    loadNodes();
  }, [setNodes, setSelectedNode, t]);

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
      loadLatestStudies(data, "latest10");
    } catch (err) {
      console.error("Recent studies failed:", err);
      setRecentError(t("errorRecent"));
    } finally {
      setRecentLoading(false);
      setStudiesLoading(false);
    }
  };

  const handleLastWeekStudies = async () => {
    if (!selectedNode) return;
    setRecentError(null);
    setRecentLoading(true);
    setStudiesLoading(true);
    try {
      const end = new Date();
      const start = subDays(end, 6);
      const data = await fetchRecentStudies({
        node_ae_title: selectedNode.ae_title,
        limit: 2000,
        study_date_from: format(start, "yyyyMMdd"),
        study_date_to: format(end, "yyyyMMdd"),
      });
      loadLatestStudies(data, "lastWeek");
    } catch (err) {
      console.error("Last week studies failed:", err);
      setRecentError(t("errorLastWeek"));
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
          {t("loadingNodes")}
        </Box>
      )}
      <Box className="flex items-center gap-3 flex-wrap">
      <FormControl size="small" className="min-w-[200px]">
        <InputLabel id="node-select-label">{t("dicomNode")}</InputLabel>
        <Select
          labelId="node-select-label"
          value={selectedNode?.ae_title || ""}
          label={t("dicomNode")}
          onChange={handleChange}
          aria-label={t("selectDicomNode")}
        >
          {nodes.map((node) => (
            <MenuItem key={node.ae_title} value={node.ae_title}>
              {node.name || node.ae_title} ({node.ae_title})
            </MenuItem>
          ))}
        </Select>
      </FormControl>

      <Tooltip title={t("echoTooltip")}>
        <span>
          <IconButton
            onClick={handleEcho}
            disabled={!selectedNode || echoLoading !== null}
            aria-label={t("testConnection")}
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
          label={
            echoStatus[selectedNode.ae_title] ? t("connected") : t("unreachable")
          }
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
        aria-label={t("latestTenAria")}
      >
        {t("latestTen")}
      </Button>
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
        onClick={handleLastWeekStudies}
        disabled={!selectedNode || recentLoading}
        className="cursor-pointer"
        aria-label={t("lastWeekAria")}
      >
        {t("lastWeek")}
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

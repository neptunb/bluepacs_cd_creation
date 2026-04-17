"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Alert, Box, CircularProgress, Typography } from "@mui/material";
import { checkCdAccess } from "@/lib/api";

type Props = {
  children: React.ReactNode;
};

const CdAccessGate = ({ children }: Props) => {
  const t = useTranslations("access");
  const [state, setState] = useState<"loading" | "ok" | "denied">("loading");

  useEffect(() => {
    let cancelled = false;
    const run = async () => {
      const ok = await checkCdAccess();
      if (!cancelled) {
        setState(ok ? "ok" : "denied");
      }
    };
    void run();
    return () => {
      cancelled = true;
    };
  }, []);

  if (state === "loading") {
    return (
      <Box
        className="flex min-h-[40vh] flex-col items-center justify-center gap-4 p-8"
        role="status"
        aria-live="polite"
        aria-busy="true"
      >
        <CircularProgress aria-hidden="true" />
        <Typography>{t("checking")}</Typography>
      </Box>
    );
  }

  if (state === "denied") {
    return (
      <Box className="mx-auto max-w-lg p-8" role="alert">
        <Alert severity="warning" className="mb-4">
          {t("deniedTitle")}
        </Alert>
        <Typography variant="body1" className="text-gray-700">
          {t("deniedBody")}
        </Typography>
      </Box>
    );
  }

  return <>{children}</>;
};

export default CdAccessGate;

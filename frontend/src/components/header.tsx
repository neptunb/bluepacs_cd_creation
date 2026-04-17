"use client";

import { useEffect, useState } from "react";
import {
  AppBar,
  Toolbar,
  Typography,
  Box,
  Button,
  ButtonGroup,
} from "@mui/material";
import AlbumIcon from "@mui/icons-material/Album";
import { useLocale, useTranslations } from "next-intl";
import { useRouter, usePathname } from "@/i18n/navigation";
import { fetchAuthIdentity } from "@/lib/api";

const Header = () => {
  const t = useTranslations("header");
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const [cfTagline, setCfTagline] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        const data = await fetchAuthIdentity();
        if (cancelled) return;
        const name = data.display_name?.trim();
        const mail = data.email?.trim();
        if (name) setCfTagline(name);
        else if (mail) setCfTagline(mail);
        else setCfTagline(null);
      } catch (e) {
        console.error("Auth identity fetch failed:", e);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const switchLocale = (next: "en" | "tr") => {
    if (next === locale) return;
    router.replace(pathname, { locale: next });
  };

  return (
    <AppBar position="static" className="bg-blue-800">
      <Toolbar>
        <AlbumIcon className="mr-3" aria-hidden />
        <Typography variant="h6" component="h1" className="font-bold">
          {t("title")}
        </Typography>
        <Box className="flex-1" />
        <Typography variant="body2" className="text-blue-200 hidden sm:block" aria-live="polite">
          {cfTagline ?? t("subtitle")}
        </Typography>
        <ButtonGroup
          size="small"
          aria-label={t("language")}
          className="ml-[15px] border border-blue-400 rounded"
        >
          <Button
            variant={locale === "en" ? "contained" : "outlined"}
            color="inherit"
            onClick={() => switchLocale("en")}
            aria-label={t("localeEn")}
            className="cursor-pointer normal-case text-white"
            sx={
              locale === "en"
                ? { bgcolor: "rgba(255,255,255,0.2)", color: "white" }
                : { borderColor: "rgba(255,255,255,0.5)", color: "white" }
            }
          >
            EN
          </Button>
          <Button
            variant={locale === "tr" ? "contained" : "outlined"}
            color="inherit"
            onClick={() => switchLocale("tr")}
            aria-label={t("localeTr")}
            className="cursor-pointer normal-case text-white"
            sx={
              locale === "tr"
                ? { bgcolor: "rgba(255,255,255,0.2)", color: "white" }
                : { borderColor: "rgba(255,255,255,0.5)", color: "white" }
            }
          >
            TR
          </Button>
        </ButtonGroup>
      </Toolbar>
    </AppBar>
  );
};

export default Header;

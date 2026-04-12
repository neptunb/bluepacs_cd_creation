"use client";

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

const Header = () => {
  const t = useTranslations("header");
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();

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
        <Typography variant="body2" className="text-blue-200 mr-4 hidden sm:block">
          {t("subtitle")}
        </Typography>
        <ButtonGroup size="small" aria-label={t("language")} className="border border-blue-400 rounded">
          <Button
            variant={locale === "en" ? "contained" : "outlined"}
            color="inherit"
            onClick={() => switchLocale("en")}
            className="cursor-pointer normal-case text-white"
            sx={
              locale === "en"
                ? { bgcolor: "rgba(255,255,255,0.2)", color: "white" }
                : { borderColor: "rgba(255,255,255,0.5)", color: "white" }
            }
          >
            {t("localeEn")}
          </Button>
          <Button
            variant={locale === "tr" ? "contained" : "outlined"}
            color="inherit"
            onClick={() => switchLocale("tr")}
            className="cursor-pointer normal-case text-white"
            sx={
              locale === "tr"
                ? { bgcolor: "rgba(255,255,255,0.2)", color: "white" }
                : { borderColor: "rgba(255,255,255,0.5)", color: "white" }
            }
          >
            {t("localeTr")}
          </Button>
        </ButtonGroup>
      </Toolbar>
    </AppBar>
  );
};

export default Header;

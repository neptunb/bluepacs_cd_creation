import { defineRouting } from "next-intl/routing";

export const routing = defineRouting({
  // Turkish: default — URLs have no locale prefix (e.g. `/`). English: `/en/...`.
  locales: ["tr", "en"],
  defaultLocale: "tr",
  localePrefix: "as-needed",
});

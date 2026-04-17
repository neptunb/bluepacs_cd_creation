import createMiddleware from "next-intl/middleware";
import { routing } from "./i18n/routing";

export default createMiddleware(routing);

// With `basePath` (e.g. /cd-yaz), matcher paths are relative to that base; include `/`
// so the base-path root is handled — see next-intl "Routing configuration" → basePath.
export const config = {
  // Exclude cf-user: Next route for Cloudflare identity (not a locale segment).
  matcher: ["/", "/((?!api|_next|_vercel|cf-user|.*\\..*).*)"],
};

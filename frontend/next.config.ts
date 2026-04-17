import type { NextConfig } from "next";
import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

// Used by rewrites (server-side proxy). Must match where Next.js can reach the API.
// Docker: set at image build time (BACKEND_INTERNAL_URL=http://cd-backend:8100).
// Local dev: http://127.0.0.1:8100 or .env.local
const backendUrl =
  process.env.BACKEND_INTERNAL_URL ||
  process.env.NEXT_PUBLIC_API_URL ||
  "http://127.0.0.1:8100";

/** Subpath behind reverse proxy (e.g. /cd-yaz). Empty for local root. */
const cdBasePath = (process.env.CD_BASE_PATH || "").trim();

const nextConfig: NextConfig = {
  output: "standalone",
  ...(cdBasePath ? { basePath: cdBasePath } : {}),
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default withNextIntl(nextConfig);

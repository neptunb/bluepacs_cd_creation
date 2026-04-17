import { NextResponse } from "next/server";
import { headers } from "next/headers";

import { identityFromHeaders } from "@/lib/cloudflare-identity";

/**
 * Cloudflare identity for the header (not under /api/* so it is not rewritten
 * to Sanic and headers() still see Cf-Access-* from the browser).
 */
export const GET = async () => {
  const h = await headers();
  const data = identityFromHeaders(h);
  return NextResponse.json(data, {
    headers: {
      "Cache-Control": "private, no-store, max-age=0",
    },
  });
};

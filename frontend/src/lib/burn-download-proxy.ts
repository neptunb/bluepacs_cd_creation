import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";

const backendBaseUrl = (): string =>
  (
    process.env.BACKEND_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://127.0.0.1:8100"
  ).replace(/\/$/, "");

const headersForUpstream = (request: NextRequest): Headers => {
  const h = new Headers();
  const cookie = request.headers.get("cookie");
  if (cookie) h.set("cookie", cookie);
  const xfHost =
    request.headers.get("x-forwarded-host") || request.headers.get("host");
  if (xfHost) h.set("x-forwarded-host", xfHost);
  const xfProto = request.headers.get("x-forwarded-proto");
  if (xfProto) h.set("x-forwarded-proto", xfProto);
  const internal =
    request.headers.get("x-internal-auth") ||
    request.headers.get("X-Internal-Auth");
  if (internal) h.set("x-internal-auth", internal);
  return h;
};

const RESPONSE_HEADER_ALLOWLIST = [
  "content-type",
  "content-disposition",
  "content-length",
  "accept-ranges",
] as const;

/**
 * Stream burn artifact downloads from Sanic without buffering multi-GB bodies
 * in the Next rewrite layer (which can fail for very large ISOs on some setups).
 */
export const proxyBurnDownload = async (
  request: NextRequest,
  backendPath: string,
): Promise<Response> => {
  const target = `${backendBaseUrl()}${backendPath}`;
  const upstream = await fetch(target, {
    method: "GET",
    cache: "no-store",
    headers: headersForUpstream(request),
    redirect: "manual",
  });

  const out = new Headers();
  for (const name of RESPONSE_HEADER_ALLOWLIST) {
    const v = upstream.headers.get(name);
    if (v) out.set(name, v);
  }

  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: out,
  });
};

import type { NextRequest } from "next/server";
import { proxyBurnDownload } from "@/lib/burn-download-proxy";

export const dynamic = "force-dynamic";

const JOB_ID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export async function GET(
  request: NextRequest,
  ctx: { params: Promise<{ jobId: string }> },
) {
  const { jobId } = await ctx.params;
  if (!jobId || !JOB_ID_RE.test(jobId)) {
    return new Response("Invalid job id", { status: 400 });
  }
  return proxyBurnDownload(request, `/api/burn/download-kpacs/${jobId}`);
}

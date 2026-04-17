/**
 * Cloudflare Access → display name (server-only: import from Route Handlers).
 * Mirrors Ultramar cloudflare-headers.php + backend/services/cloudflare_identity.py.
 */

const jwtPayloadUnverified = (token: string): Record<string, unknown> | null => {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payload = parts[1].replaceAll("-", "+").replaceAll("_", "/");
    const pad = "=".repeat((4 - (payload.length % 4)) % 4);
    const json = Buffer.from(payload + pad, "base64").toString("utf8");
    return JSON.parse(json) as Record<string, unknown>;
  } catch {
    return null;
  }
};

const nameFromPayload = (payload: Record<string, unknown>): string | null => {
  const name = payload.name;
  if (typeof name === "string" && name.trim()) return name.trim();
  const gn = typeof payload.given_name === "string" ? payload.given_name.trim() : "";
  const fn = typeof payload.family_name === "string" ? payload.family_name.trim() : "";
  const combined = [gn, fn].filter(Boolean).join(" ").trim();
  return combined || null;
};

const emailFromPayload = (payload: Record<string, unknown>): string | null => {
  for (const key of ["email", "preferred_username"] as const) {
    const v = payload[key];
    if (typeof v === "string" && v.includes("@")) return v.trim();
  }
  return null;
};

export type AuthIdentityPayload = {
  display_name: string | null;
  email: string | null;
};

/** Read Cloudflare Access identity from the incoming request headers. */
export const identityFromHeaders = (h: Headers): AuthIdentityPayload => {
  const email =
    h.get("cf-access-authenticated-user-email")?.trim() ||
    h.get("Cf-Access-Authenticated-User-Email")?.trim() ||
    null;

  const userName =
    h.get("cf-access-user-name")?.trim() ||
    h.get("Cf-Access-User-Name")?.trim() ||
    null;
  if (userName) {
    return { display_name: userName, email };
  }

  const jwt =
    h.get("cf-access-jwt-assertion")?.trim() ||
    h.get("Cf-Access-Jwt-Assertion")?.trim() ||
    null;
  if (!jwt) {
    return { display_name: null, email };
  }

  const payload = jwtPayloadUnverified(jwt);
  if (!payload) {
    return { display_name: null, email };
  }

  const resolvedEmail = email || emailFromPayload(payload);

  const display = nameFromPayload(payload);
  if (display) {
    return { display_name: display, email: resolvedEmail };
  }

  return {
    display_name: null,
    email: resolvedEmail,
  };
};

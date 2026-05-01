/** Extract a human-readable error message from a FastAPI error response. */
export function formatApiError(data: unknown, fallback: string): string {
  if (data && typeof data === "object") {
    const d = data as Record<string, unknown>;
    if (typeof d.detail === "string") return d.detail;
    if (Array.isArray(d.detail)) {
      return d.detail
        .map((e: unknown) => {
          if (e && typeof e === "object") {
            const err = e as Record<string, unknown>;
            const loc = Array.isArray(err.loc) ? err.loc.join(".") : "";
            const msg = typeof err.msg === "string" ? err.msg : "";
            return loc ? `${loc}: ${msg}` : msg;
          }
          return String(e);
        })
        .filter(Boolean)
        .join("; ");
    }
    if (typeof d.error === "string") return d.error;
    if (typeof d.message === "string") return d.message;
  }
  return fallback;
}

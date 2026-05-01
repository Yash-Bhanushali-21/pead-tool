/** Format an ISO date string or datetime as YYYY-MM-DD only. */
export function formatYmdOnly(iso: string | null | undefined): string {
  if (!iso) return "";
  return iso.slice(0, 10);
}

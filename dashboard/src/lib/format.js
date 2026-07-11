/** Normalize AI business_impact values to CRITICAL | HIGH | MEDIUM | LOW. */
export function normalizeImpact(value) {
  const raw = String(value || "")
    .trim()
    .toUpperCase();
  for (const level of ["CRITICAL", "HIGH", "MEDIUM", "LOW"]) {
    if (raw === level || raw.startsWith(`${level} `) || raw.includes(level)) {
      return level;
    }
  }
  return "UNKNOWN";
}

export function formatTimestamp(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime())) return String(value);
  return d.toLocaleString();
}

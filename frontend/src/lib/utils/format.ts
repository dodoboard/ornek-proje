export function formatMegabytes(mb: number): string {
  if (!Number.isFinite(mb) || mb < 0) return "—";
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${Math.round(mb)} MB`;
}

export function formatGigabytes(gb: number): string {
  if (!Number.isFinite(gb) || gb < 0) return "—";
  return `${gb.toFixed(1)} GB`;
}

/** Percentage clamped to 0–100; returns 0 when the total is not positive. */
export function percent(part: number, total: number): number {
  if (!(total > 0) || !Number.isFinite(part)) return 0;
  return Math.min(100, Math.max(0, (part / total) * 100));
}

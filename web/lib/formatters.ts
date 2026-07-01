/** Format a number in millions to $X.XXB / $X.XXT / $XXXM */
export function fmtMn(mn: number | null | undefined): string {
  if (mn == null) return "N/A";
  const abs = Math.abs(mn);
  if (abs >= 1_000_000) return `$${(mn / 1_000_000).toFixed(2)}T`;
  if (abs >= 1_000) return `$${(mn / 1_000).toFixed(2)}B`;
  return `$${mn.toFixed(0)}M`;
}

/** Format raw dollars (not millions) */
export function fmtNum(n: number | null | undefined): string {
  if (n == null) return "N/A";
  const abs = Math.abs(n);
  if (abs >= 1e12) return `$${(n / 1e12).toFixed(2)}T`;
  if (abs >= 1e9) return `$${(n / 1e9).toFixed(2)}B`;
  if (abs >= 1e6) return `$${(n / 1e6).toFixed(1)}M`;
  return `$${n.toLocaleString()}`;
}

/** Format a ratio (e.g. 0.2427) as "24.3%" */
export function fmtPct(n: number | null | undefined, decimals = 1): string {
  if (n == null) return "N/A";
  return `${(n * 100).toFixed(decimals)}%`;
}

/** Format a raw percentage (e.g. 24.3 → "24.3%") */
export function fmtPctRaw(n: number | null | undefined, decimals = 1): string {
  if (n == null) return "N/A";
  return `${n.toFixed(decimals)}%`;
}

/** Format a price */
export function fmtPrice(n: number | null | undefined): string {
  if (n == null) return "N/A";
  return `$${n.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

/** Short date — "Jun 30, 2026" */
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/** CAGR formatted from raw ratio */
export function fmtCagr(n: number | null | undefined): string {
  if (n == null) return "N/A";
  return `${(n * 100).toFixed(1)}%`;
}

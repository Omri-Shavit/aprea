// Display helpers. Real harvested rows carry many nulls (registry and literature
// rows often have no p-value, effect size or direction), so every value that
// reaches the DOM goes through one of these and renders as an em dash when absent.

export const EMPTY = "—";

export function isBlank(v) {
  return v === null || v === undefined || v === "" || (typeof v === "number" && !Number.isFinite(v));
}

export function txt(v) {
  return isBlank(v) ? EMPTY : String(v);
}

// Numbers with a sensible number of significant digits; very small/large values
// (real IC50s, p-values) fall back to exponential notation.
export function num(v, digits = 3) {
  if (isBlank(v)) return EMPTY;
  const n = Number(v);
  if (!Number.isFinite(n)) return EMPTY;
  if (n === 0) return "0";
  const abs = Math.abs(n);
  if (abs < 1e-3 || abs >= 1e6) return n.toExponential(2);
  return String(Number(n.toPrecision(digits)));
}

// Exact display for counts. num() rounds to significant digits, which is right
// for a measured IC50 but wrong for a row count: 12947 studies must never render
// as "12900".
export function count(v) {
  if (isBlank(v)) return EMPTY;
  const n = Number(v);
  if (!Number.isFinite(n)) return EMPTY;
  return Math.round(n).toLocaleString("en-US");
}

export function pct(v, digits = 0) {
  if (isBlank(v)) return EMPTY;
  const n = Number(v);
  if (!Number.isFinite(n)) return EMPTY;
  return `${n.toFixed(digits)}%`;
}

// Fraction in [0,1] -> percent string.
export function fracPct(v, digits = 0) {
  if (isBlank(v)) return EMPTY;
  const n = Number(v);
  if (!Number.isFinite(n)) return EMPTY;
  return `${(n * 100).toFixed(digits)}%`;
}

export function asArray(v) {
  return Array.isArray(v) ? v : [];
}

// Only keep finite numbers — recharts renders NaN as a broken axis. Nulls and
// empty strings must not slip through as 0 (Number(null) === 0).
export function finiteNum(v) {
  if (v === null || v === undefined || v === "") return null;
  const n = Number(v);
  return Number.isFinite(n) ? n : null;
}

// The composition endpoint may return either {key: count} objects or arrays of
// {name, count} / {key, count} records depending on the field. Normalise both.
export function toCounts(input) {
  if (!input) return [];
  if (Array.isArray(input)) {
    return input
      .map((d) => ({
        name: String(d?.name ?? d?.key ?? d?.label ?? ""),
        count: finiteNum(d?.count ?? d?.n ?? d?.total ?? d?.value) ?? 0,
      }))
      .filter((d) => d.name !== "");
  }
  if (typeof input === "object") {
    return Object.entries(input)
      .map(([name, count]) => ({ name: String(name), count: finiteNum(count) ?? 0 }))
      .filter((d) => d.name !== "");
  }
  return [];
}

export function humanize(key) {
  if (!key) return "";
  return String(key).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// Joins an aliases field that may arrive as an array or a delimited string.
export function joinList(v, sep = ", ") {
  if (Array.isArray(v)) {
    const parts = v.filter((x) => !isBlank(x)).map(String);
    return parts.length ? parts.join(sep) : EMPTY;
  }
  return txt(v);
}

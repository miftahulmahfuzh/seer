// Pure geometry for Sera's hand-built SVG charts: scales, ticks, path builders, label layout and
// tick formatters. No React, no DOM, no snapshot import, so it is unit-tested under plain vitest.

export type Domain = readonly [number, number];
export type Pt = readonly [number, number];
export type Tick = { value: number; label: string };
/** A line across the plot at one value: a gate threshold, zero, SPY. */
export type RefLine = { value: number; label?: string; color?: string; dash?: string; tip?: string };
/** A target tick count, or an explicit list of ticks (then no formatter is needed). */
export type TickSpec = number | readonly Tick[];
export type Format = (v: number) => string;

/** Colour cycle for series that do not set their own. Seer v2 tokens only. */
export const CHART_COLORS = ['var(--ink)', 'var(--line-b)', 'var(--line-c)', 'var(--coral)', 'var(--pos)', 'var(--ink-3)'] as const;

export function colorAt(i: number): string {
  const n = CHART_COLORS.length;
  return CHART_COLORS[((i % n) + n) % n];
}

export const isNum = (v: number | null | undefined): v is number => typeof v === 'number' && Number.isFinite(v);

/** `v` held inside [a, b], whichever order a and b come in. */
export function clamp(v: number, a: number, b: number): number {
  const lo = Math.min(a, b);
  const hi = Math.max(a, b);
  return Math.min(hi, Math.max(lo, v));
}

/** Linear map from `domain` onto `range`. A zero-width domain maps everything to the middle of the range. */
export function linear(domain: Domain, range: Domain): (v: number) => number {
  const [d0, d1] = domain;
  const [r0, r1] = range;
  if (d1 === d0) {
    const mid = (r0 + r1) / 2;
    return () => mid;
  }
  const k = (r1 - r0) / (d1 - d0);
  return v => r0 + (v - d0) * k;
}

/** [min, max] of the finite values plus `include`. Empty: [0, 1]. A single value is padded by 10% (or 1 at zero). */
export function extent(values: Iterable<number | null | undefined>, include: readonly number[] = []): Domain {
  let lo = Infinity;
  let hi = -Infinity;
  for (const v of values) {
    if (!isNum(v)) continue;
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  for (const v of include) {
    if (!isNum(v)) continue;
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  if (lo === Infinity) return [0, 1];
  if (lo === hi) {
    const pad = lo === 0 ? 1 : Math.abs(lo) * 0.1;
    return [lo - pad, hi + pad];
  }
  return [lo, hi];
}

/** A 1, 2, 2.5 or 5 × 10^k step that cuts `span` into about `count` intervals. */
export function niceStep(span: number, count: number): number {
  if (!(span > 0) || !Number.isFinite(span)) return 1;
  const raw = span / Math.max(1, count);
  const mag = 10 ** Math.floor(Math.log10(raw));
  const norm = raw / mag;
  const nice = norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 2.5 ? 2.5 : norm <= 5 ? 5 : 10;
  return nice * mag;
}

function tidy(v: number, step: number): number {
  const digits = Math.min(12, Math.max(0, 2 - Math.floor(Math.log10(step))));
  return Number(v.toFixed(digits)) || 0;
}

/** Ticks on a nice step; the first is <= min and the last is >= max. */
export function niceTicks(min: number, max: number, count = 5): number[] {
  if (!isNum(min) || !isNum(max)) return [];
  if (min === max) return [min];
  const lo = Math.min(min, max);
  const hi = Math.max(min, max);
  const step = niceStep(hi - lo, count);
  const first = Math.floor(lo / step + 1e-9);
  const last = Math.ceil(hi / step - 1e-9);
  const out: number[] = [];
  for (let i = first; i <= last; i++) out.push(tidy(i * step, step));
  return out;
}

/** Nice ticks that fall inside `domain` (the domain itself is kept as given). */
export function ticksWithin(domain: Domain, count = 5): number[] {
  const lo = Math.min(domain[0], domain[1]);
  const hi = Math.max(domain[0], domain[1]);
  const eps = (hi - lo) * 1e-9;
  return niceTicks(lo, hi, count).filter(t => t >= lo - eps && t <= hi + eps);
}

/** [min, max] widened out to the nice ticks around it. */
export function niceDomain(min: number, max: number, count = 5): Domain {
  const t = niceTicks(min, max, count);
  return t.length >= 2 ? [t[0], t[t.length - 1]] : extent([min, max]);
}

/**
 * One value axis. Explicit ticks win (the domain then covers them and `raw`). Otherwise nice ticks:
 * inside `domain` when one is given, or over `raw` with the domain widened to the outer ticks.
 */
export function resolveAxis(
  raw: Domain,
  opts: { domain?: Domain; ticks?: TickSpec; format: Format; count: number },
): { domain: Domain; ticks: Tick[] } {
  const spec = opts.ticks;
  if (spec !== undefined && typeof spec !== 'number') {
    const ticks = [...spec];
    return { domain: opts.domain ?? extent(ticks.map(t => t.value), [raw[0], raw[1]]), ticks };
  }
  const count = spec ?? opts.count;
  if (opts.domain) {
    return { domain: opts.domain, ticks: ticksWithin(opts.domain, count).map(v => ({ value: v, label: opts.format(v) })) };
  }
  const vals = niceTicks(raw[0], raw[1], count);
  const domain: Domain = vals.length >= 2 ? [vals[0], vals[vals.length - 1]] : raw;
  return { domain, ticks: vals.map(v => ({ value: v, label: opts.format(v) })) };
}

/** '1993-01-29' (UTC midnight) or a full ISO timestamp -> epoch ms. */
export function dateNum(iso: string): number {
  return Date.parse(iso.length === 10 ? `${iso}T00:00:00Z` : iso);
}

const MONTH_YEAR = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', month: 'short', year: 'numeric' });

/**
 * Jan-1 ticks every 1, 2, 5, 10… years so there are at most `maxTicks`, inside [min, max] (epoch ms).
 * A window too short for two year marks gets its two ends instead ('Oct 2015', 'Mar 2016').
 */
export function yearTicks(min: number, max: number, maxTicks = 12): Tick[] {
  if (!isNum(min) || !isNum(max) || max <= min) return [];
  const y0 = new Date(min).getUTCFullYear();
  const y1 = new Date(max).getUTCFullYear();
  const years = y1 - y0 + 1;
  const step = [1, 2, 5, 10, 20, 50, 100].find(st => Math.ceil(years / st) <= maxTicks) ?? 100;
  const out: Tick[] = [];
  for (let y = Math.ceil(y0 / step) * step; y <= y1; y += step) {
    const v = Date.UTC(y, 0, 1);
    if (v >= min && v <= max) out.push({ value: v, label: String(y) });
  }
  if (out.length >= 2) return out;
  return [
    { value: min, label: MONTH_YEAR.format(new Date(min)) },
    { value: max, label: MONTH_YEAR.format(new Date(max)) },
  ];
}

const r1 = (v: number) => Math.round(v * 10) / 10 || 0;

/** SVG path through the points; a null (or non-finite) point lifts the pen. Coordinates to 0.1. */
export function linePath(points: ReadonlyArray<Pt | null>): string {
  let d = '';
  let pen = false;
  for (const p of points) {
    if (!p || !isNum(p[0]) || !isNum(p[1])) {
      pen = false;
      continue;
    }
    d += `${pen ? 'L' : 'M'}${r1(p[0])} ${r1(p[1])}`;
    pen = true;
  }
  return d;
}

/** Closed area between each unbroken run of points and the horizontal line y = baseY. */
export function areaPath(points: ReadonlyArray<Pt | null>, baseY: number): string {
  let d = '';
  let run: Pt[] = [];
  const flush = () => {
    if (run.length > 1) {
      d += `M${r1(run[0][0])} ${r1(baseY)}`;
      for (const p of run) d += `L${r1(p[0])} ${r1(p[1])}`;
      d += `L${r1(run[run.length - 1][0])} ${r1(baseY)}Z`;
    }
    run = [];
  };
  for (const p of points) {
    if (p && isNum(p[0]) && isNum(p[1])) run.push(p);
    else flush();
  }
  flush();
  return d;
}

/** Step-after: holds each value flat until the next x (for "best so far" lines). Nulls still break the line. */
export function stepPoints(points: ReadonlyArray<Pt | null>): Array<Pt | null> {
  const out: Array<Pt | null> = [];
  let prev: Pt | null = null;
  for (const p of points) {
    if (p && prev) out.push([p[0], prev[1]]);
    out.push(p);
    prev = p;
  }
  return out;
}

/** Moves label positions apart to at least `gap`, inside [lo, hi], keeping their order. Returned in input order. */
export function spread(values: readonly number[], gap: number, lo = -Infinity, hi = Infinity): number[] {
  const order = values.map((_, i) => i).sort((a, b) => values[a] - values[b]);
  const pos = order.map(i => values[i]);
  for (let k = 0; k < pos.length; k++) pos[k] = Math.max(pos[k], lo, k ? pos[k - 1] + gap : -Infinity);
  for (let k = pos.length - 1; k >= 0; k--) pos[k] = Math.min(pos[k], hi, k < pos.length - 1 ? pos[k + 1] - gap : Infinity);
  const out = new Array<number>(values.length);
  order.forEach((i, k) => {
    out[i] = pos[k];
  });
  return out;
}

/** Rough rendered width of `text` in Outfit at `size` user units (for margins, not layout-critical). */
export const textWidth = (text: string, size = 13) => text.length * size * 0.56;

/** `text` cut to at most `max` characters with an ellipsis. */
export function truncate(text: string, max: number): string {
  return text.length <= max ? text : `${text.slice(0, Math.max(1, max - 1)).trimEnd()}…`;
}

// ---- Tick formatters (factories, so a page writes yFormat={fmtPct(0)}) -------------------------

const MINUS = '−';
const signFor = (v: number, shown: string, plus: boolean) => (Number(shown) === 0 ? '' : v < 0 ? MINUS : plus ? '+' : '');

/** 0.153 -> '15%', -0.153 -> '−15%'. */
export const fmtPct = (digits = 0): Format => v => {
  const shown = (Math.abs(v) * 100).toFixed(digits);
  return `${signFor(v, shown, false)}${shown}%`;
};
/** 0.0123 -> '+1.2%' with digits 1. */
export const fmtSignedPct = (digits = 0): Format => v => {
  const shown = (Math.abs(v) * 100).toFixed(digits);
  return `${signFor(v, shown, true)}${shown}%`;
};
/** -3 -> '−3'. */
export const fmtNumber = (digits = 0): Format => v => {
  const shown = Math.abs(v).toFixed(digits);
  return `${signFor(v, shown, false)}${shown}`;
};
/** 2.5 -> '2.5×' (growth of 1). */
export const fmtMultiple = (digits = 1): Format => v => `${v.toFixed(digits)}×`;

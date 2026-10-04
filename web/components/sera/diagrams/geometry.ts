// Pure layout math for the hand-built SVG diagrams on /sera/how. No React, no snapshot.

export type Box = { x: number; y: number; w: number; h: number };

/** One box of the pipeline diagram. Lines are pre-broken: SVG text does not wrap. */
export type PipelineStage = {
  key: string;
  /** 1–2 short lines (≤ 14 characters each). */
  title: string[];
  /** 1–5 short lines (≤ 18 characters, ≤ 26 on a weight-1.35 box). */
  detail: string[];
  /** The pill at the bottom, e.g. '58 tries'. */
  count: string;
  /** Tooltip on the pill. */
  countTip: string;
  /** Draws a dashed "fails" arrow from this box down to the journal lane. */
  fails: boolean;
  /** Relative width; 1 when omitted. */
  weight?: number;
  /** The last stage (real money) gets the accent fill. */
  final?: boolean;
};

/** A dated stretch of history, e.g. a bear market. Dates are ISO yyyy-mm-dd. */
export type Era = { start: string; end: string; label: string; years: string };

/** Boxes left to right across `width`, sized by `weights`, separated by `gap`. */
export function rowBoxes(weights: number[], width: number, gap: number, y: number, h: number): Box[] {
  if (weights.length === 0) return [];
  const total = weights.reduce((a, w) => a + w, 0);
  const unit = (width - gap * (weights.length - 1)) / total;
  const out: Box[] = [];
  let x = 0;
  for (const w of weights) {
    out.push({ x, y, w: w * unit, h });
    x += w * unit + gap;
  }
  return out;
}

const toTime = (iso: string) => Date.parse(`${iso.slice(0, 10)}T00:00:00Z`);

/** Linear date -> x over [start, end] onto [x0, x1], clamped to the range. */
export function timeScale(start: string, end: string, x0: number, x1: number): (iso: string) => number {
  const t0 = toTime(start);
  const span = toTime(end) - t0 || 1;
  return (iso: string) => {
    const f = Math.min(1, Math.max(0, (toTime(iso) - t0) / span));
    return x0 + f * (x1 - x0);
  };
}

/** Years divisible by `step` after start's year, up to end's year. */
export function yearTicks(start: string, end: string, step: number): number[] {
  const y0 = Number(start.slice(0, 4));
  const y1 = Number(end.slice(0, 4));
  const out: number[] = [];
  for (let y = Math.ceil((y0 + 1) / step) * step; y <= y1; y += step) out.push(y);
  return out;
}

const MONTH_YEAR = new Intl.DateTimeFormat('en-US', { timeZone: 'UTC', month: 'short', year: 'numeric' });

/** '2015-10-16' -> 'Oct 2015' */
export const monthYear = (iso: string) => MONTH_YEAR.format(new Date(`${iso.slice(0, 10)}T12:00:00Z`));

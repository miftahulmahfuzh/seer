/**
 * Pure reshaping of the lab snapshot for the /sera pages.
 *
 * Pass/fail always comes from the engine's `trial.failed` (invariant 5: the web never
 * re-judges a trial). The gate is used only to print targets.
 */
import { pct, signedPct } from '../format';
import type { Benchmark, Gate, LabMethod, LabTrial, Point } from './types';

export const CONDITION_KEYS = ['spy', 'drawdown', 'pf', 'trades', 'owner', 'dsr'] as const;
export type ConditionKey = (typeof CONDITION_KEYS)[number];

/**
 * The engine's label for each condition, exactly as it appears in `trial.failed`.
 *
 * The luck check is the exception and is matched by prefix instead (`DSR_FAILURE_PREFIX`):
 * `trials` is append-only, so a trial judged before the owner moved the bar on 2026-10-07 carries
 * `DSR >= 0.95` for ever and one judged after carries `DSR >= 0.90`. Both mean "missed the luck
 * check", and matching one literal would quietly render the other as a pass.
 */
export const FAILURE_LABEL: Record<Exclude<ConditionKey, 'dsr' | 'drawdown'>, string> = {
  spy: 'beats SPY TR',
  pf: 'PF >= 1.3',
  trades: '>= 100 trades',
  owner: 'owner inputs',
};

/**
 * The two labels that carry a threshold in their own text, and so must be matched by prefix.
 *
 * `trials` is append-only, so a row judged before 2026-10-07 carries `DSR >= 0.95` and
 * `max DD <= 15%` for ever, while a row judged after carries `DSR >= 0.90` and `max DD <= 20%` —
 * the owner moved both bars that day. Matching either literal would render the other as a
 * **pass**, which is the worst failure this page has: a missed hurdle shown as a green tick.
 *
 * These mirror `store.LUCK_LABEL_PREFIX` and the live `dev.FAILURE_LABELS` drawdown entry; the
 * engine-side pins in Steps 9 and 14 are what keep the mirror honest.
 */
export const DSR_FAILURE_PREFIX = 'DSR >= ';
export const DRAWDOWN_FAILURE_PREFIX = 'max DD <= ';

/** Plain-language name of each condition. */
export const CONDITION_LABEL: Record<ConditionKey, string> = {
  spy: 'Beats SPY',
  drawdown: 'Max drawdown',
  pf: 'Profit factor',
  trades: 'Trade count',
  owner: 'Owner inputs',
  dsr: 'Luck check',
};

/** `ok` is null when the condition was never measured (historical trials have no luck check). */
export type GateCheck = { key: ConditionKey; label: string; value: string; target: string; ok: boolean | null };
export type FunnelRow = { key: ConditionKey; label: string; passing: number; measured: number; total: number };
export type ProgressPoint = { n: number; passed: number; bestPassed: number; mar: number | null; bestMar: number | null };
export type FamilyRow = {
  family: string;
  methodIds: string[];
  trials: number;
  bestMar: number | null;
  bestPassed: number;
  historical: boolean;
};
export type YearReturn = { year: number; ret: number };

const DASH = '—';

const perYear = (v: number | null) => (v === null ? DASH : `${signedPct(v, 1)} a year`);
const num = (v: number) => String(Number(v.toFixed(4)));

export const devTrials = (trials: LabTrial[]): LabTrial[] => trials.filter((t) => t.window === 'dev');

const byN = (a: LabTrial, b: LabTrial) => a.n - b.n;

/** Higher MAR first; a missing MAR sorts last. */
function marDesc(a: LabTrial, b: LabTrial): number {
  if (a.mar === b.mar) return 0;
  if (a.mar === null) return 1;
  if (b.mar === null) return -1;
  return b.mar - a.mar;
}

/** true = passed, false = missed, null = not measured. */
export function conditionOk(trial: LabTrial, key: ConditionKey): boolean | null {
  if (key === 'dsr') {
    if (trial.failed.some((f) => f.startsWith(DSR_FAILURE_PREFIX))) return false;
    return trial.dsr === null ? null : true;
  }
  if (key === 'drawdown') {
    return !trial.failed.some((f) => f.startsWith(DRAWDOWN_FAILURE_PREFIX));
  }
  if (trial.failed.includes(FAILURE_LABEL[key])) return false;
  return true;
}

/** The six hurdles for one trial, in display order, with plain labels and display strings. */
export function gateChecks(trial: LabTrial, gate: Gate): GateCheck[] {
  const pf = trial.pfInfinite
    ? '∞ (no losing trades)'
    : trial.profitFactor === null
      ? DASH
      : trial.profitFactor.toFixed(2);
  const ownerMissed = conditionOk(trial, 'owner') === false;
  return [
    {
      key: 'spy',
      label: CONDITION_LABEL.spy,
      value: perYear(trial.cagr),
      target: trial.spyTrCagr === null ? 'more than SPY' : `more than ${perYear(trial.spyTrCagr)}`,
      ok: conditionOk(trial, 'spy'),
    },
    {
      key: 'drawdown',
      label: CONDITION_LABEL.drawdown,
      value: trial.maxDrawdown === null ? DASH : `${pct(trial.maxDrawdown, 1)} at worst`,
      target: `${pct(gate.maxDrawdown, 0)} or less`,
      ok: conditionOk(trial, 'drawdown'),
    },
    {
      key: 'pf',
      label: CONDITION_LABEL.pf,
      value: pf,
      target: `${num(gate.minProfitFactor)} or more`,
      ok: conditionOk(trial, 'pf'),
    },
    {
      key: 'trades',
      label: CONDITION_LABEL.trades,
      value: String(trial.trades),
      target: `${gate.minTrades} or more`,
      ok: conditionOk(trial, 'trades'),
    },
    {
      key: 'owner',
      label: CONDITION_LABEL.owner,
      value: ownerMissed ? 'needs owner input' : 'none needed',
      target: 'none needed',
      ok: conditionOk(trial, 'owner'),
    },
    {
      key: 'dsr',
      label: CONDITION_LABEL.dsr,
      value: trial.dsr === null ? 'not measured' : trial.dsr.toFixed(2),
      target: `${num(gate.dsrMin)} or more`,
      ok: conditionOk(trial, 'dsr'),
    },
  ];
}

/** How many of the six hurdles the trial cleared (not-measured counts as not cleared). */
export function conditionsPassed(trial: LabTrial): number {
  return CONDITION_KEYS.filter((k) => conditionOk(trial, k) === true).length;
}

/** The hurdles the trial missed, in display order. */
export function misses(trial: LabTrial): ConditionKey[] {
  return CONDITION_KEYS.filter((k) => conditionOk(trial, k) === false);
}

/** CAGR minus SPY total-return CAGR over the same window. */
export function excessCagr(trial: LabTrial): number | null {
  if (trial.cagr === null || trial.spyTrCagr === null) return null;
  return trial.cagr - trial.spyTrCagr;
}

/** The k dev trials nearest to eligible: most hurdles cleared, then best MAR, then earliest. */
export function closest(trials: LabTrial[], k: number): LabTrial[] {
  return devTrials(trials)
    .sort((a, b) => conditionsPassed(b) - conditionsPassed(a) || marDesc(a, b) || byN(a, b))
    .slice(0, k);
}

/** A method's best variant: fewest missed hurdles, then best MAR, then earliest. Dev trials first. */
export function bestVariant(trials: LabTrial[]): LabTrial | null {
  const dev = devTrials(trials);
  const pool = dev.length > 0 ? dev : [...trials];
  if (pool.length === 0) return null;
  return pool.sort((a, b) => misses(a).length - misses(b).length || marDesc(a, b) || byN(a, b))[0];
}

/** Per hurdle, how many dev trials cleared it. */
export function funnel(trials: LabTrial[]): FunnelRow[] {
  const dev = devTrials(trials);
  return CONDITION_KEYS.map((key) => {
    const oks = dev.map((t) => conditionOk(t, key));
    return {
      key,
      label: CONDITION_LABEL[key],
      passing: oks.filter((o) => o === true).length,
      measured: oks.filter((o) => o !== null).length,
      total: dev.length,
    };
  });
}

/** Over trial number: each dev trial's own score plus the best seen so far. */
export function progress(trials: LabTrial[]): ProgressPoint[] {
  const out: ProgressPoint[] = [];
  let bestPassed = 0;
  let bestMar: number | null = null;
  for (const t of devTrials(trials).sort(byN)) {
    const passed = conditionsPassed(t);
    bestPassed = Math.max(bestPassed, passed);
    if (t.mar !== null && (bestMar === null || t.mar > bestMar)) bestMar = t.mar;
    out.push({ n: t.n, passed, bestPassed, mar: t.mar, bestMar });
  }
  return out;
}

/** Methods and dev trials grouped by family; most-tried family first. */
export function families(methods: LabMethod[], trials: LabTrial[]): FamilyRow[] {
  const familyOf = new Map(methods.map((m) => [m.id, m.family]));
  const rows = new Map<string, FamilyRow>();
  for (const m of methods) {
    const row = rows.get(m.family);
    if (row) {
      row.methodIds.push(m.id);
      row.historical = row.historical && m.historical;
    } else {
      rows.set(m.family, {
        family: m.family,
        methodIds: [m.id],
        trials: 0,
        bestMar: null,
        bestPassed: 0,
        historical: m.historical,
      });
    }
  }
  for (const t of devTrials(trials)) {
    const family = familyOf.get(t.methodId);
    const row = family === undefined ? undefined : rows.get(family);
    if (!row) continue;
    row.trials += 1;
    row.bestPassed = Math.max(row.bestPassed, conditionsPassed(t));
    if (t.mar !== null && (row.bestMar === null || t.mar > row.bestMar)) row.bestMar = t.mar;
  }
  return [...rows.values()].sort((a, b) => b.trials - a.trials || a.family.localeCompare(b.family));
}

/** Trials grouped by method id, each list ordered by n. */
export function trialsByMethod(trials: LabTrial[]): Map<string, LabTrial[]> {
  const out = new Map<string, LabTrial[]>();
  for (const t of [...trials].sort(byN)) {
    const list = out.get(t.methodId);
    if (list) list.push(t);
    else out.set(t.methodId, [t]);
  }
  return out;
}

/** Value of the last point dated on or before `date`, or null when every point is later. */
function valueAtOrBefore(series: Point[], date: string): number | null {
  let lo = 0;
  let hi = series.length - 1;
  let found = -1;
  while (lo <= hi) {
    const mid = (lo + hi) >> 1;
    if (series[mid][0] <= date) {
      found = mid;
      lo = mid + 1;
    } else {
      hi = mid - 1;
    }
  }
  return found === -1 ? null : series[found][1];
}

/**
 * SPY total return over the trial's own window, rebased so the trial's start = 1.0, on the
 * trial's curve dates. Base = the last benchmark point dated on or before `trial.start`, or
 * the first point. Curve dates past the benchmark's end are dropped.
 */
export function spyForWindow(trial: LabTrial, benchmark: Benchmark): Point[] {
  const spy = benchmark.spyTr;
  if (spy.length === 0 || trial.curve.length === 0) return [];
  const base = valueAtOrBefore(spy, trial.start) ?? spy[0][1];
  const last = spy[spy.length - 1][0];
  const out: Point[] = [];
  for (const [d] of trial.curve) {
    if (d > last) break;
    const v = valueAtOrBefore(spy, d);
    if (v === null) continue;
    out.push([d, v / base]);
  }
  return out;
}

/** Underwater series: value / running peak − 1 (≤ 0). The peak starts at the base 1.0. */
export function drawdownSeries(curve: Point[]): Point[] {
  let peak = 1;
  return curve.map(([d, v]) => {
    peak = Math.max(peak, v);
    return [d, v / peak - 1];
  });
}

/** Calendar-year returns. The first year runs from the curve's base 1.0; the last may be partial. */
export function yearlyReturns(curve: Point[]): YearReturn[] {
  const out: YearReturn[] = [];
  let prev = 1;
  let year: number | null = null;
  let lastValue = 1;
  for (const [d, v] of curve) {
    const y = Number(d.slice(0, 4));
    if (year !== null && y !== year) {
      out.push({ year, ret: lastValue / prev - 1 });
      prev = lastValue;
    }
    year = y;
    lastValue = v;
  }
  if (year !== null) out.push({ year, ret: lastValue / prev - 1 });
  return out;
}

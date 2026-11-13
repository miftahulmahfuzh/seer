/**
 * Pure reshaping of the lab snapshot for the /sera pages.
 *
 * Pass/fail always comes from the engine (invariant 5: the web never re-judges a trial), and
 * the gate is used only to print targets. **Which** engine answer, though, is the whole
 * question: `trial.failed` is what the lab said on the run date, and `trial.failedNow` is what
 * the same row is judged as today. Reading the first while printing targets out of `gate` is
 * how the method page came to render `Luck check: no (0.912 < 0.90)` — the cross from a row
 * recorded against the old 0.95 bar, the number from the live one beside it.
 *
 * So: every pass/fail here reads `failedNow`, and `failed` is displayed only where the page
 * says it is showing the record (the technical detail block). The web still does not re-judge
 * anything — it must not, because the luck test is not `dsr >= gate.dsrMin`; re-scoring a DSR
 * at today's N is arithmetic the engine holds (`store.dsr_at`).
 *
 * The same rule covers **which hurdles a row has**, not only how it did on them. A hurdle the
 * engine never applied is absent from `failedNow`, and absence read as a pass is the worst
 * failure this page has: a missed hurdle shown as a green tick. So the one hurdle that does not
 * apply to every row — the luck check, which a pre-registered test look has no selection to
 * deflate — is read off the engine's own marker, `trial.luckGated`, and never inferred from the
 * shape of `failedNow`.
 *
 * The seventh hurdle, the random-twin check, has the same trap one condition over: an arm nobody
 * has measured carries no label in `failedNow`, and neither does one that cleared. So it is read
 * off the engine's published reading, `trial.yardstick`, through `twinsState`, and an arm with no
 * reading is "not measured yet" — never a tick. A control arm is a third kind of thing again: the
 * engine refuses it with a label that is not a condition, and the page shows it as a comparison
 * book rather than as an idea that failed.
 */
import { pct, signedPct } from '../format';
import type { Benchmark, Gate, LabBook, LabMethod, LabTrial, Point } from './types';

export const CONDITION_KEYS = ['spy', 'drawdown', 'pf', 'trades', 'owner', 'dsr', 'yardstick'] as const;
export type ConditionKey = (typeof CONDITION_KEYS)[number];

/**
 * The engine's label for each condition, exactly as it appears in a failure list.
 *
 * Three are matched by shape instead (`DSR_FAILURE_PREFIX`, `DRAWDOWN_FAILURE_PREFIX`,
 * `isYardstickLabel`), because each carries its bar inside its own text. `failedNow` always names
 * today's bar, so an exact match would work there — but `failed` does not, the two lists are read
 * by the same helpers, and a shape match cannot go stale the next time the owner moves a bar.
 */
export const FAILURE_LABEL: Record<Exclude<ConditionKey, 'dsr' | 'drawdown' | 'yardstick'>, string> = {
  spy: 'beats SPY TR',
  pf: 'PF >= 1.3',
  trades: '>= 100 trades',
  owner: 'owner inputs',
};

/**
 * The two labels that carry a threshold in their own text, and so must be matched by prefix.
 *
 * `trials` is append-only, so the *record* (`failed`) on a row judged before 2026-10-07 carries
 * `DSR >= 0.95` and `max DD <= 15%` for ever; the *verdict* (`failedNow`) always carries today's
 * `DSR >= 0.90` and `max DD <= 20%`. Matching either literal would render the other as a
 * **pass**, which is the worst failure this page has: a missed hurdle shown as a green tick.
 *
 * These mirror `store.LUCK_LABEL_PREFIX` and the live `dev.FAILURE_LABELS` drawdown entry; the
 * engine-side pins in Steps 9 and 14 are what keep the mirror honest.
 */
export const DSR_FAILURE_PREFIX = 'DSR >= ';
export const DRAWDOWN_FAILURE_PREFIX = 'max DD <= ';

/**
 * The random-twin label (`store.YARDSTICK_LABEL`, "beats 90% of random twins"), matched by its two
 * fixed ends with a number between them.
 *
 * Its bar sits in the middle of the text, so a prefix alone cannot do what it does for the luck
 * and drawdown labels: `beats ` is also how `beats SPY TR` begins. Both ends plus a number is the
 * narrowest shape that still reads the label after the owner moves the bar.
 * `engine/tests/test_lab_gate_wording.py` pins both ends, and the number, to the engine.
 */
export const YARDSTICK_FAILURE_PREFIX = 'beats ';
export const YARDSTICK_FAILURE_SUFFIX = '% of random twins';

export function isYardstickLabel(label: string): boolean {
  if (!label.startsWith(YARDSTICK_FAILURE_PREFIX) || !label.endsWith(YARDSTICK_FAILURE_SUFFIX)) return false;
  const bar = label.slice(YARDSTICK_FAILURE_PREFIX.length, label.length - YARDSTICK_FAILURE_SUFFIX.length);
  return /^\d+(\.\d+)?$/.test(bar);
}

/**
 * What the engine adds to a control arm's verdict (`store.CONTROL_LABEL`).
 *
 * It is not a condition and is never drawn as a seventh crossed hurdle. A control arm is a book
 * the lab built to be beaten, so the idea beside it has something fair to be measured against;
 * its not becoming a candidate is the design working, not an idea failing. The page presents it
 * as a comparison book instead (`isComparisonBook`). Pinned by `engine/tests/test_lab_gate_wording.py`.
 */
export const CONTROL_LABEL = 'not a control arm';

/** Is this arm a comparison book rather than a candidate? Its recorded role, or the engine's own label. */
export function isComparisonBook(trial: LabTrial): boolean {
  return trial.role === 'control' || trial.failedNow.includes(CONTROL_LABEL);
}

/** Plain-language name of each condition. */
export const CONDITION_LABEL: Record<ConditionKey, string> = {
  spy: 'Beats SPY',
  drawdown: 'Max drawdown',
  pf: 'Profit factor',
  trades: 'Trade count',
  owner: 'Owner inputs',
  dsr: 'Luck check',
  yardstick: 'Beats look-alikes',
};

/**
 * `ok` is null only when a condition cannot be decided either way. The luck check is never null:
 * a DSR that cannot be evaluated is a luck test that was not passed (the engine's D11), so those
 * rows come back `false` with "not measured" as their value.
 */
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

/**
 * The pair a **funded** trial is read on, or null when it is not one: what its money actually
 * earned, against the same deposits put into SPY on the same days.
 *
 * Both or neither, and that is not tidiness — it is the engine's own branch. `dev.beats_spy_tr`
 * uses the money-weighted pair only `if mwr is not None and spy_mwr is not None`, and otherwise
 * decides `beats SPY TR` on total return exactly as it does for an unfunded row. A page that read
 * one of the two alone would print a number the tick beside it was not decided on.
 *
 * Why anything reads this at all: once money goes in after the start, `totalReturn` and `cagr`
 * stop being returns. On one measured funded run the engine reports a total return of +1078% and
 * an earned rate of 7.6% for the *same* run; the difference is the owner's own deposits piling up.
 */
export function moneyWeighted(trial: LabTrial): { mwr: number; spyTrMwr: number } | null {
  if (trial.mwr === null || trial.spyTrMwr === null) return null;
  return { mwr: trial.mwr, spyTrMwr: trial.spyTrMwr };
}

/**
 * Where an arm stands on the random-twin check, read off the engine and never re-judged.
 *
 * - `cleared`: a measured reading, and the engine lists no random-twin miss.
 * - `missed`: the engine lists the miss. With a reading, the arm was below the bar; without one,
 *   it was run after the check began and nobody measured it, which the engine fails closed.
 * - `unmatched`: the look-alikes ended up trading too differently to be a fair comparison. Never
 *   a pass, whatever the engine's list says.
 * - `not-applicable`: the book only holds funds, so there are no picked stocks to swap.
 * - `not-measured`: no reading and no miss — every arm the lab held when the check began.
 *   Neither a pass nor a miss, and never drawn as either.
 * - `test-look`: a test-window run. The check is a development-stage hurdle.
 */
export type TwinsState = 'cleared' | 'missed' | 'unmatched' | 'not-applicable' | 'not-measured' | 'test-look';

export function twinsState(trial: LabTrial): TwinsState {
  const y = trial.yardstick;
  if (trial.failedNow.some(isYardstickLabel)) return y?.status === 'unmatched' ? 'unmatched' : 'missed';
  if (trial.window !== 'dev') return 'test-look';
  if (y === null) return 'not-measured';
  if (y.status === 'not-applicable') return 'not-applicable';
  if (y.status === 'unmatched') return 'unmatched';
  return 'cleared';
}

/**
 * A share in words, as "N in D" with the smallest of 10, 20, 100 or 1000 that makes N whole:
 * 0.9 -> "9 in 10", 0.95 -> "19 in 20". The owner reads "9 in 10" without a percent sign to parse.
 */
export function shareInWords(share: number): string {
  for (const d of [10, 20, 100, 1000]) {
    const k = share * d;
    if (Math.abs(k - Math.round(k)) < 1e-9) return `${Math.round(k)} in ${d}`;
  }
  return `${Math.round(share * 1000)} in 1000`;
}

/** The reading as printed beside its mark: "beat 187 of 200", or why there is none. */
export function twinsValue(trial: LabTrial): string {
  const y = trial.yardstick;
  const beat = y !== null && y.beaten !== null && y.draws !== null ? `beat ${y.beaten} of ${y.draws}` : null;
  switch (twinsState(trial)) {
    case 'cleared':
      return beat ?? 'cleared';
    case 'missed':
      return beat ?? 'not measured';
    case 'unmatched':
      return 'look-alikes traded too differently to compare';
    case 'not-applicable':
    case 'test-look':
      return 'does not apply';
    case 'not-measured':
      return 'not measured yet';
  }
}

/** What the arm had to do, in words, with the bar read from the snapshot's gate. */
export function twinsTarget(trial: LabTrial, gate: Gate): string {
  switch (twinsState(trial)) {
    case 'test-look':
      return 'does not apply to a test look';
    case 'not-applicable':
      return 'does not apply to a book that only holds funds';
    default:
      return `beats at least ${shareInWords(gate.yardstickMin)} random look-alike books`;
  }
}

/**
 * Does this trial clear `key` **as the bars read now**? true = cleared, false = missed,
 * null = there is no hurdle to score here.
 *
 * Reads `failedNow`, `luckGated` and `yardstick`, never `failed`. The engine decided all seven
 * there (`store.published_verdict`) against the same gate the snapshot publishes, and said which
 * rows the luck hurdle applies to (`store.luck_gated`), so this is a lookup, not a judgement —
 * which is what keeps a tick and the target printed beside it from describing two different days.
 *
 * `null` is "not applicable" for the luck check (a test look) and for the random-twin check (a
 * test look, or a book that only holds funds), and — for the random-twin check only — "not
 * measured yet". It is never a pass: every count here counts only `true`. A gated row whose DSR
 * could not be scored still comes back `false`: the engine puts the luck label in `failedNow` for
 * exactly those rows, because nothing is admitted for being unmeasurable (its D11).
 */
export function conditionOk(trial: LabTrial, key: ConditionKey): boolean | null {
  if (key === 'yardstick') {
    const state = twinsState(trial);
    if (state === 'cleared') return true;
    if (state === 'missed' || state === 'unmatched') return false;
    return null;
  }
  if (key === 'dsr') {
    if (!trial.luckGated) return null;
    return !trial.failedNow.some((f) => f.startsWith(DSR_FAILURE_PREFIX));
  }
  if (key === 'drawdown') return !trial.failedNow.some((f) => f.startsWith(DRAWDOWN_FAILURE_PREFIX));
  return !trial.failedNow.includes(FAILURE_LABEL[key]);
}

/** The seven hurdles for one trial, in display order, with plain labels and display strings. */
export function gateChecks(trial: LabTrial, gate: Gate): GateCheck[] {
  const pf = trial.pfInfinite
    ? '∞ (no losing trades)'
    : trial.profitFactor === null
      ? DASH
      : trial.profitFactor.toFixed(2);
  const ownerMissed = conditionOk(trial, 'owner') === false;
  const money = moneyWeighted(trial);
  return [
    {
      key: 'spy',
      label: CONDITION_LABEL.spy,
      // A funded row is decided on what its money earned, not on its curve's shape, so those are
      // the numbers printed beside the tick. Reading `cagr` here on such a row would quote a
      // figure the engine never judged it by — the same defect as `0.912 < 0.90`, one field over.
      value: perYear(money === null ? trial.cagr : money.mwr),
      target:
        money !== null
          ? `more than ${perYear(money.spyTrMwr)} from the same deposits in SPY`
          : trial.spyTrCagr === null
            ? 'more than SPY'
            : `more than ${perYear(trial.spyTrCagr)}`,
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
      // `dsrNow`, not `dsr`: the score at the gate's N, which is the N `gate.dsrMin` is the bar
      // for. The recorded `dsr` belongs to the N of its own run date and is shown as the record.
      value: trial.dsrNow === null ? 'not measured' : trial.dsrNow.toFixed(2),
      // A test look is scored but not gated, so quoting the bar beside its number would invent a
      // hurdle the lab never set it.
      target: trial.luckGated ? `${num(gate.dsrMin)} or more` : 'does not apply to a test look',
      ok: conditionOk(trial, 'dsr'),
    },
    {
      key: 'yardstick',
      label: CONDITION_LABEL.yardstick,
      value: twinsValue(trial),
      target: twinsTarget(trial, gate),
      ok: conditionOk(trial, 'yardstick'),
    },
  ];
}

/**
 * How many of the seven hurdles the trial cleared. Not-measured luck counts as not cleared (the
 * engine already listed it as a failure); a hurdle that does not apply, or a random-twin check
 * nobody has run yet, counts as neither cleared nor missed, so a test look reads 4 of 5.
 */
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

/**
 * The k dev trials nearest to eligible: most hurdles cleared, then best MAR, then earliest.
 * Comparison books are left out: they are built to be beaten and are never "nearly there".
 */
export function closest(trials: LabTrial[], k: number): LabTrial[] {
  return devTrials(trials)
    .filter((t) => !isComparisonBook(t))
    .sort((a, b) => conditionsPassed(b) - conditionsPassed(a) || marDesc(a, b) || byN(a, b))
    .slice(0, k);
}

/**
 * A method's best variant: fewest missed hurdles, then best MAR, then earliest. Dev trials first,
 * and among them the candidates: a comparison book clears the six classic hurdles as easily as an
 * idea does (that is what makes it a fair comparison), so letting it win here would headline the
 * method with the arm registered to lose. It is chosen only when the method has nothing else.
 */
export function bestVariant(trials: LabTrial[]): LabTrial | null {
  const dev = devTrials(trials);
  const candidates = dev.filter((t) => !isComparisonBook(t));
  const pool = candidates.length > 0 ? candidates : dev.length > 0 ? dev : [...trials];
  if (pool.length === 0) return null;
  return pool.sort((a, b) => misses(a).length - misses(b).length || marDesc(a, b) || byN(a, b))[0];
}

/** Could this hurdle be scored on this row at all? The denominator `funnel` quotes. */
function scored(t: LabTrial, key: ConditionKey): boolean {
  if (key === 'dsr') return t.luckGated && t.dsrNow !== null;
  if (key === 'yardstick') {
    const state = twinsState(t);
    return state === 'cleared' || state === 'missed' || state === 'unmatched';
  }
  return true;
}

/**
 * Per hurdle, how many dev trials cleared it.
 *
 * `measured` is how many rows the hurdle could be *scored* on. For most hurdles that is every
 * row. The luck check leaves out the P7a seed rows, which have no DSR to re-evaluate at any N;
 * those rows still **miss** it — nothing is admitted for being unmeasurable, and `passing` counts
 * them as misses — but "1 of the 56 it was checked on" rather than "1 of 110" is the honest
 * denominator. The random-twin check counts only rows that have been judged on it (a reading, or
 * the engine's miss): an arm nobody has measured was not checked, and one that only holds funds
 * has nothing to check.
 *
 * `luckGated` is checked alongside the score for the same reason the denominator exists at all:
 * a row the hurdle does not apply to was not "checked and unscorable", it was not checked.
 */
export function funnel(trials: LabTrial[]): FunnelRow[] {
  const dev = devTrials(trials);
  return CONDITION_KEYS.map((key) => ({
    key,
    label: CONDITION_LABEL[key],
    passing: dev.filter((t) => conditionOk(t, key) === true).length,
    measured: dev.filter((t) => scored(t, key)).length,
    total: dev.length,
  }));
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

// ---- Books: one strategy, several method ids --------------------------------------------------

/**
 * One strategy as the page shows it: the row, and the other names folded under it.
 *
 * A method id is not a strategy, and the two places that mattered most were both getting it
 * wrong in a way that cost the owner. The buy signal named three methods and they were one book,
 * which read as three independent reasons to spend real money. The spent-look counter said four
 * and the looks had bought two, which made the evidence against the lab's own approach look
 * twice as strong as it is. Neither number is hidden here — the others are kept beside the lead
 * so a collapsed row can be opened.
 */
export type Book = {
  lead: { id: string; name: string };
  /** `why` is already a finished sentence with the lead's **name** in it, never its id. */
  others: { id: string; name: string; why: string }[];
};

/**
 * `snapshot.books` entries with the method names filled in.
 *
 * The engine ships each reason with `{lead}` still in it precisely so this substitution happens
 * once, here: the terminal report fills the same template with ids and the correlation that
 * confirmed it, and the owner's page may carry neither. What goes in here is **"this one"**, not
 * the lead's name — these sentences are always rendered directly beneath the lead's own row, and
 * a lab method's name is a full sentence of its own, so repeating it turns a four-word reason
 * into a paragraph. The name is still carried on `lead` for whoever needs to print it.
 *
 * An id with no method row falls back to the id, which is the only thing left to show.
 */
export function books(rows: LabBook[], methods: LabMethod[]): Book[] {
  const nameOf = new Map(methods.map(m => [m.id, m.name]));
  return rows.map(b => ({
    lead: { id: b.lead, name: nameOf.get(b.lead) ?? b.lead },
    others: b.others.map(id => ({
      id,
      name: nameOf.get(id) ?? id,
      why: (b.why[id] ?? 'the same strategy as {lead}').replace('{lead}', 'this one'),
    })),
  }));
}

// Pure helpers for the Leaderboard: roster-driven looks, the common-window comparison that ranks
// research strategies honestly, the honest checklist line and the month-by-month rows. No data
// access; page.tsx feeds it.
// Selection (`selectStrategy`) and icons (`strategyIcon`) are phase 11's `components/roster.ts`;
// short labels are phase 10's `Strategy.short`; the month math is phase 10's `lib/monthly.ts`.
//
// `compare` is a TypeScript port of the engine's `seer_engine/paper/compare.py`
// (roster-promotion-pipeline phase 3): the same window rule, the same selection, the same metrics,
// the same `insufficient` cut, the same rank order. The leaderboard is a server component
// rendering inside a request and cannot run the Python CLI, so the math is ported rather than
// called; `compare.py` stays the reference implementation and its tests are the specification.
// MIN_COMMON_SESSIONS, MIN_RANKED, the selection rule and the rank key must all stay equal to it:
// a leaderboard that ranks differently from `python -m seer_engine compare` is worse than either
// being wrong alone, because nothing says which one to believe. Pin new fixtures against
// `compare --json`.
import { monthDay, monthName, pct, signedPct } from '../../../lib/format';
import type { Snapshot } from '../../../lib/metrics';
import type { MonthlyTable } from '../../../lib/monthly';

/** The roster fields these helpers read (a structural subset of lib/data's Strategy). */
export type RosterIn = { id: string; isChampion: boolean; isBenchmark: boolean };

/**
 * What the ranking reads: the roster fields plus phase 1's lifecycle column. Structurally equal to
 * `lib/data`'s `Strategy['status']`, so a `Strategy` satisfies `RankIn` with no import (view.ts
 * must not pull in `lib/data`, which opens a database connection).
 */
export type RankIn = RosterIn & { status: 'active' | 'retired' };

/**
 * Research strategies take the design's sheet and line pairs in roster order: the A/B/C pairs, then
 * butter (the fourth sheet of the design's slot palette) with the coral accent line, so a fourth
 * research strategy (C · News veto) never reuses the first one's look.
 *
 * The roster is variable length — a promotion adds a horseman and a retirement keeps one on the
 * board — so neither array may be assumed to cover it. They are cycled independently and their
 * lengths are coprime, so the (sheet, line) pair a strategy gets is unique for the first
 * `LOOK_PERIOD` research strategies. Both tokens are defined for light and dark in `globals.css`.
 */
export const CARD_BGS = ['bg-lav', 'bg-sky', 'bg-stone', 'bg-butter'] as const;
export const LINES = ['var(--ink)', 'var(--line-b)', 'var(--line-c)', 'var(--coral)', 'var(--ink-2)'] as const;

/** lcm(CARD_BGS.length, LINES.length): research strategies before any (sheet, line) pair repeats. */
export const LOOK_PERIOD = 20;

export type Look = { bg: string; line: string; width: number; dotted: boolean };

export const LOOK_FALLBACK: Look = { bg: 'bg-sheet', line: 'var(--ink-2)', width: 2, dotted: false };

/** Card sheet and chart line per strategy id, by roster order. The benchmark is the dotted line on a plain sheet. */
export function looks(roster: RosterIn[]): Map<string, Look> {
  const out = new Map<string, Look>();
  let i = 0;
  for (const st of roster) {
    if (st.isBenchmark) {
      out.set(st.id, { bg: 'bg-sheet', line: 'var(--ink-3)', width: 1.75, dotted: true });
      continue;
    }
    out.set(st.id, {
      bg: CARD_BGS[i % CARD_BGS.length],
      line: LINES[i % LINES.length],
      width: st.isChampion ? 2.75 : 2,
      dotted: false,
    });
    i += 1;
  }
  return out;
}

/**
 * The month-by-month sheet's tint: the strategy's card sheet, except butter, which on mobile would
 * merge into the butter checklist sheet stacked right above it; that one takes stone instead.
 */
export const monthsBg = (look: Look): string => (look.bg === 'bg-butter' ? 'bg-stone' : look.bg);

export const researchOf = <T extends RosterIn>(roster: T[]): T[] => roster.filter(st => !st.isBenchmark);

/**
 * Sessions a strategy must share with the others before it can be ranked. **This is
 * `compare.py`'s `MIN_COMMON_SESSIONS` and must stay equal to it** — 63, one quarter of a
 * 252-session year, which is three full rebalances for a monthly-hold book strategy, so a ranked
 * strategy has made at least three independent decisions inside the window. A three-week-old
 * method does not win a leaderboard, and a window shorter than this is not a ranking, it is noise.
 */
export const MIN_COMMON_SESSIONS = 63;

/** `compare.py`'s `MIN_RANKED`. A ranking of one is not a comparison. */
export const MIN_RANKED = 2;

const DAY = 86_400_000;
const TRADING_DAYS = 252;

/** The window a comparison ranked over: its first and last shared session, and how many there were. */
export type CompareWindow = { from: string; to: string; sessions: number };

/**
 * 'ranked'       — compared over the whole common window; every windowed figure is a number.
 * 'insufficient' — too few shared sessions to rank (a newcomer, or a window that is still short).
 * 'retired'      — stopped trading; its record stands, but it is never ranked against the living.
 *
 * 'ranked' and 'insufficient' are `compare.py`'s own two statuses, spelled identically. 'retired'
 * is a UI-side **pre-filter outcome** that the engine module never sees: a retired strategy is
 * dropped before the window is computed, exactly as `compare --exclude <id>` drops it on the CLI
 * side (phase 3's Handoffs settle this). Windowed figures are non-null **only** for 'ranked'.
 */
export type CompareStatus = 'ranked' | 'insufficient' | 'retired';

export type CompareRow<T extends RankIn = RankIn> = {
  strategy: T;
  status: CompareStatus;
  /** Sessions ranked over ('ranked'), else the strategy's own snapshot count. */
  sessions: number;
  /** Over the common window. Null unless `status` is 'ranked'. */
  totalReturn: number | null;
  cagr: number | null;
  maxDrawdown: number | null;
  sharpe: number | null;
  /** Inception to date, over the strategy's own whole record. Never mixed into the ranking. */
  inception: number | null;
};

export type Comparison<T extends RankIn = RankIn> = {
  /**
   * The window the ranking used. **Null exactly when nothing is ranked** — `compare.py`'s own
   * guarantee (`window === null ⟺ no row has status 'ranked'`), so a window on the page is always
   * a window something was actually ranked over.
   */
  window: CompareWindow | null;
  /**
   * How many sessions every live research strategy currently shares, ranked or not. Presentation
   * only: it is what lets `windowLine` say how far off a ranking is instead of showing a blank.
   * It is never a window and nothing is ever ranked over it.
   */
  shared: number;
  /** Every research strategy, benchmark excluded, in roster order. Nothing is ever dropped. */
  rows: CompareRow<T>[];
  /** The rankable subset, best first. Empty while the window is too short. */
  ranked: CompareRow<T>[];
  best: CompareRow<T> | null;
};

const byDate = (a: Snapshot, b: Snapshot) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0);

/**
 * Every date all of `curves` have: the set intersection, ascending. [] for no curves.
 * This is `compare.py`'s `_common_dates`, character for character in intent — a plain
 * intersection, NOT `[max(start), min(end)]`, so a session one strategy missed is dropped for
 * every strategy and all of them are measured over the very same consecutive pairs of dates.
 */
function commonDates(curves: Snapshot[][]): string[] {
  if (curves.length === 0) return [];
  const sets = curves.map(c => new Set(c.map(p => p.date)));
  return [...sets[0]].filter(d => sets.every(s => s.has(d))).sort();
}

/** Inception-to-date total return over a strategy's whole record; null with fewer than two snapshots. */
function inceptionOf(curve: Snapshot[]): number | null {
  if (curve.length < 2) return null;
  const c = [...curve].sort(byDate);
  return c[0].equity === 0 ? null : c[c.length - 1].equity / c[0].equity - 1;
}

type Windowed = {
  totalReturn: number; cagr: number | null; maxDrawdown: number; sharpe: number | null;
};

/** The window's figures for one curve, which must have a snapshot on every date in `dates`. */
function windowed(curve: Snapshot[], dates: string[]): Windowed {
  const on = new Map(curve.map(p => [p.date, p.equity]));
  const eq = dates.map(d => on.get(d)!);
  const start = eq[0], end = eq[eq.length - 1];

  let peak = start, maxDrawdown = 0;
  for (const v of eq) {
    if (v > peak) peak = v;
    if (peak > 0) maxDrawdown = Math.max(maxDrawdown, (peak - v) / peak);
  }

  const years = (Date.parse(dates[dates.length - 1]) - Date.parse(dates[0])) / DAY / 365.25;
  const cagr = years > 0 && start > 0 ? Math.pow(end / start, 1 / years) - 1 : null;

  const rets: number[] = [];
  for (let i = 1; i < eq.length; i++) if (eq[i - 1] !== 0) rets.push(eq[i] / eq[i - 1] - 1);
  let sharpe: number | null = null;
  if (rets.length >= 2) {
    const mean = rets.reduce((a, v) => a + v, 0) / rets.length;
    const sd = Math.sqrt(rets.reduce((a, v) => a + (v - mean) ** 2, 0) / (rets.length - 1));
    sharpe = sd > 0 ? (mean / sd) * Math.sqrt(TRADING_DAYS) : null;
  }

  return { totalReturn: start === 0 ? 0 : end / start - 1, cagr, maxDrawdown, sharpe };
}

/**
 * Best first, and this is `compare.py`'s `_rank_key` with the signs flipped into a comparator:
 * finite Sharpe descending; rows with no Sharpe last; then total return descending; then the
 * SMALLER max drawdown; then the id. Every tie is broken, so the order never depends on the order
 * the rows arrived in — the property `test_selection_is_independent_of_input_order` pins on the
 * Python side.
 */
function rankCmp<T extends RankIn>(a: CompareRow<T>, b: CompareRow<T>): number {
  const ag = a.sharpe === null ? 1 : 0, bg = b.sharpe === null ? 1 : 0;
  if (ag !== bg) return ag - bg;
  if (ag === 0 && a.sharpe !== b.sharpe) return (b.sharpe as number) - (a.sharpe as number);
  const ar = a.totalReturn ?? 0, br = b.totalReturn ?? 0;
  if (ar !== br) return br - ar;
  const ad = a.maxDrawdown ?? 0, bd = b.maxDrawdown ?? 0;
  if (ad !== bd) return ad - bd;
  return a.strategy.id < b.strategy.id ? -1 : a.strategy.id > b.strategy.id ? 1 : 0;
}

/**
 * Who gets ranked, and over which dates — `compare.py`'s `_select`, ported.
 *
 * First every curve shorter than `MIN_COMMON_SESSIONS` on its own is dropped, so one young
 * strategy cannot shorten the window for the board. Then, while the intersection is still short,
 * the strategy whose removal leaves the LONGEST intersection goes (ties: the shortest own curve,
 * then the id) and the intersection is recomputed. It stops when the intersection is long enough,
 * or when fewer than `MIN_RANKED` strategies remain — in which case nothing is ranked at all.
 *
 * The greedy drop is the half this plan originally left out, and it is the half that matters: a
 * board of four where one strategy barely overlaps still produces a ranking of the other three
 * here, exactly as the CLI does, instead of ranking nothing.
 */
function selectRanked(
  curves: Map<string, Snapshot[]>, minSessions: number,
): { ids: Set<string>; dates: string[] } {
  const own = (id: string) => curves.get(id)!;
  let live = [...curves.keys()].filter(id => own(id).length >= minSessions).sort();
  while (live.length >= MIN_RANKED) {
    const common = commonDates(live.map(own));
    if (common.length >= minSessions) return { ids: new Set(live), dates: common };
    if (live.length === MIN_RANKED) break;
    let worst = live[0];
    let worstKey: [number, number, string] | null = null;
    for (const id of live) {
      const rest = live.filter(o => o !== id);
      const key: [number, number, string] = [-commonDates(rest.map(own)).length, own(id).length, id];
      if (worstKey === null || key[0] < worstKey[0]
        || (key[0] === worstKey[0] && key[1] < worstKey[1])
        || (key[0] === worstKey[0] && key[1] === worstKey[1] && key[2] < worstKey[2])) {
        worst = id;
        worstKey = key;
      }
    }
    live = live.filter(id => id !== worst);
  }
  return { ids: new Set(), dates: [] };
}

/**
 * Rank the research strategies over the window they actually share (R3, invariant 6).
 *
 * A TypeScript port of `seer_engine/paper/compare.py`'s `compare`, selection rule included. The
 * window is the intersection of the selected strategies' snapshot dates (`selectRanked`), and it
 * is returned rather than implied; `window` is null exactly when nothing could be ranked, which is
 * the engine module's own guarantee.
 *
 * Two filters happen HERE and not in the engine module, because they are roster semantics rather
 * than arithmetic — `compare.py` is deliberately blind to both:
 *
 * - **The benchmark is never compared.** It is the yardstick, not a method.
 * - **A retired strategy is never ranked, and never dropped from `rows`.** It keeps its card and
 *   its inception-to-date figure (invariant 4) and is excluded from the window, so a retirement
 *   cannot shorten the living strategies' comparison. On the CLI side the same exclusion is
 *   `compare --exclude <id>`.
 */
export function compare<T extends RankIn>(rows: { strategy: T; curve: Snapshot[] }[]): Comparison<T> {
  const research = rows.filter(r => !r.strategy.isBenchmark);
  const live = research.filter(r => r.strategy.status === 'active' && r.curve.length >= 2);
  const curves = new Map(live.map(r => [r.strategy.id, [...r.curve].sort(byDate)]));

  const { ids: rankedIds, dates } = selectRanked(curves, MIN_COMMON_SESSIONS);
  const window: CompareWindow | null = dates.length > 0
    ? { from: dates[0], to: dates[dates.length - 1], sessions: dates.length }
    : null;
  // How much the LIVE board shares right now, ranked or not. Never a ranking; only the sentence
  // that says how far off one is.
  const shared = commonDates([...curves.values()]).length;

  const out: CompareRow<T>[] = research.map(r => {
    const base = {
      strategy: r.strategy,
      sessions: r.curve.length,
      inception: inceptionOf(r.curve),
      totalReturn: null,
      cagr: null,
      maxDrawdown: null,
      sharpe: null,
    };
    if (r.strategy.status === 'retired') return { ...base, status: 'retired' as const };
    if (!rankedIds.has(r.strategy.id)) return { ...base, status: 'insufficient' as const };
    return {
      strategy: r.strategy,
      status: 'ranked' as const,
      sessions: dates.length,
      inception: base.inception,
      ...windowed(curves.get(r.strategy.id)!, dates),
    };
  });

  const ranked = out.filter(r => r.status === 'ranked').sort(rankCmp);
  return { window, shared, rows: out, ranked, best: ranked[0] ?? null };
}

/** The two lines that put the ranking's window on the page. */
export type WindowLine = { label: string; detail: string };

/**
 * The sentence that makes the window visible (invariant 6): the leaderboard never shows a "best"
 * without saying, next to it, over which sessions it was best. With no window yet it says how far
 * off one is instead of quietly showing a number that compares unequal records.
 */
export function windowLine(c: Comparison): WindowLine {
  const compared = c.ranked.length;
  const active = c.rows.filter(r => r.strategy.status === 'active').length;
  if (compared === 0) {
    // `c.window` is null here by construction, so the honest number is `c.shared` — the sessions
    // the live board has in common so far. Saying "0 of 63" when four strategies share 40 would be
    // its own small lie.
    return {
      label: 'No common window yet',
      detail: `${c.shared} of ${MIN_COMMON_SESSIONS} sessions shared by every strategy`,
    };
  }
  const w = c.window!;
  return {
    label: `Ranked over ${monthDay(w.from)} – ${monthDay(w.to)}`,
    detail: `${w.sessions} shared sessions · ${compared} of ${active} active strategies compared`,
  };
}

/**
 * The benchmark's return over exactly the span `curve` covers. "Beats SPY" must compare the two
 * over the same dates once strategies can start on different days (invariant 6); SPY's own
 * inception-to-date figure is its record, not the comparison. Null when the benchmark has no
 * snapshot on one of the two boundary dates.
 */
export function spyOverSpan(spy: Snapshot[], curve: Snapshot[]): number | null {
  if (curve.length < 2) return null;
  const c = [...curve].sort(byDate);
  const on = new Map(spy.map(p => [p.date, p.equity]));
  const a = on.get(c[0].date), b = on.get(c[c.length - 1].date);
  return a === undefined || b === undefined || a === 0 ? null : b / a - 1;
}

/**
 * The research strategy the page shows: the requested id when it is on the roster, else the first
 * **active** one, else the first row. Retired strategies stay selectable — retirement preserves the
 * record (invariant 4), it does not hide it — but the default never lands on one while a live
 * strategy exists.
 */
export function pickResearch<T extends RankIn>(research: T[], requested: string | undefined): T | null {
  return research.find(r => r.id === requested)
    ?? research.find(r => r.status === 'active')
    ?? research[0]
    ?? null;
}

/** 'Retired Dec 2' for the card's marker; plain 'Retired' until `paper_end` is written (phase 2). */
export const retiredLabel = (paperEnd: string | null): string =>
  paperEnd === null ? 'Retired' : `Retired ${monthDay(paperEnd)}`;

/** Design §1's five rules plus "Backtest gate passed". */
export const CHECKS = 6;

export type Score = { passed: number; total: number; ready: boolean; lines: [string, string] };

/** The gate fields the score reads (a structural subset of lib/strategy's Gate). */
export type GateIn = { passed: boolean; applicable: boolean };

/** A strategy with no checklist yet: not passed, applicable. */
export const NO_GATE: GateIn = { passed: false, applicable: true };

/**
 * The checklist score and its two-line verdict. Never "Ready for real money" unless all six pass,
 * and never for a strategy whose backtest item is not applicable (C, handover D9): real money for
 * it would need an explicit owner decision even if the five forward rules pass.
 */
export function scoreOf(items: { ok: boolean }[], gate: GateIn): Score {
  const passed = items.filter(i => i.ok).length;
  const ready = gate.applicable && items.length === CHECKS && passed === CHECKS;
  const lines: [string, string] = !gate.applicable
    ? ['Paper only. No backtest gate.', 'Real money needs an owner decision']
    : ready
      ? ['All six pass.', 'Ready for real money']
      : gate.passed
        ? ['Paper trading until', 'all six pass']
        : ['Paper only.', 'Backtest gate not passed'];
  return { passed, total: CHECKS, ready, lines };
}

export type Cell = { text: string; tone: '' | 'pos' | 'neg' };

export type MonthLine = {
  key: string;
  label: string;
  partial: boolean;
  ret: Cell;
  spy: string;
  trades: string;
  drop: string;
};

const toned = (v: number | null): Cell =>
  v === null ? { text: '—', tone: '' } : { text: signedPct(v, 1), tone: v < 0 ? 'neg' : 'pos' };
const plain = (v: number | null) => (v === null ? '—' : signedPct(v, 1));

/** '2026-10' -> 'Oct 2026' */
export const monthLabel = (ym: string) => `${monthName(`${ym}-01`)} ${ym.slice(0, 4)}`;

/** Month rows of phase 10's MonthlyTable, newest first (monthly() returns them oldest first). */
export function monthLines(t: MonthlyTable): MonthLine[] {
  return [...t.months]
    .sort((a, b) => b.month.localeCompare(a.month))
    .map(r => ({
      key: r.month,
      label: monthLabel(r.month),
      partial: r.partial,
      ret: toned(r.return),
      spy: plain(r.spyReturn),
      trades: String(r.trades),
      drop: pct(r.worstDrop, 1),
    }));
}

/** The since-start total row (from day 0); null before the first paper session. */
export function sinceStartLine(t: MonthlyTable): MonthLine | null {
  const ss = t.sinceStart;
  if (ss === null) return null;
  return {
    key: 'since-start',
    label: `Since ${monthDay(ss.from)}`,
    partial: false,
    ret: toned(ss.return),
    spy: plain(ss.spyReturn),
    trades: String(ss.trades),
    drop: pct(ss.worstDrop, 1),
  };
}

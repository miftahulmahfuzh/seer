// Pure helpers for the Leaderboard: roster-driven looks, the best research strategy, the honest
// checklist line and the month-by-month rows. No data access; page.tsx feeds it.
// Selection (`selectStrategy`) and icons (`strategyIcon`) are phase 11's `components/roster.ts`;
// short labels are phase 10's `Strategy.short`; the month math is phase 10's `lib/monthly.ts`.
import { monthDay, monthName, pct, signedPct } from '../../../lib/format';
import type { MonthlyTable } from '../../../lib/monthly';

/** The roster fields these helpers read (a structural subset of lib/data's Strategy). */
export type RosterIn = { id: string; isChampion: boolean; isBenchmark: boolean };

/**
 * Research strategies take the design's sheet and line pairs in roster order: the A/B/C pairs, then
 * butter (the fourth sheet of the design's slot palette) with the coral accent line, so a fourth
 * research strategy (C · News veto) never reuses the first one's look.
 */
export const CARD_BGS = ['bg-lav', 'bg-sky', 'bg-stone', 'bg-butter'] as const;
export const LINES = ['var(--ink)', 'var(--line-b)', 'var(--line-c)', 'var(--coral)'] as const;

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
      line: i < LINES.length ? LINES[i] : 'var(--ink-2)',
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

/** Highest total return among research strategies that have one. */
export function bestResearch<T extends RosterIn>(
  rows: { strategy: T; metrics: { totalReturn: number | null } }[],
): { strategy: T; ret: number } | null {
  let best: { strategy: T; ret: number } | null = null;
  for (const r of rows) {
    const v = r.metrics.totalReturn;
    if (r.strategy.isBenchmark || v === null) continue;
    if (best === null || v > best.ret) best = { strategy: r.strategy, ret: v };
  }
  return best;
}

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

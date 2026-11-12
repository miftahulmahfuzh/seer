// Pure helpers for the Leaderboard: roster-driven looks, the common-window comparison that ranks
// research strategies honestly, the honest checklist line and the month-by-month rows. No data
// access; page.tsx feeds it.
// Selection (`selectStrategy`) and icons (`strategyIcon`, and `displayIcons` that makes them unique
// per roster) are `components/roster.ts`; short labels are phase 10's `Strategy.short`; the month
// math is phase 10's `lib/monthly.ts`.
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
import { CHECKLIST_RULES, type Snapshot } from '../../../lib/metrics';
import type { MonthlyTable } from '../../../lib/monthly';
import { attachedOriginal } from '../../../lib/strategy';

/**
 * The roster fields these helpers read (a structural subset of lib/data's Strategy). `twinOf` is
 * optional so a fixture without twins still type-checks; lib/data always sets it.
 */
export type RosterIn = { id: string; isChampion: boolean; isBenchmark: boolean; twinOf?: string | null };

/**
 * What the ranking reads: the roster fields plus phase 1's lifecycle column. Structurally equal to
 * `lib/data`'s `Strategy['status']`, so a `Strategy` satisfies `RankIn` with no import (view.ts
 * must not pull in `lib/data`, which opens a database connection).
 */
export type RankIn = RosterIn & { status: 'active' | 'retired' };

/**
 * Every research strategy gets a sheet of its own, and a Claude twin gets the sheet next to its
 * original's. The palette is six families, each a base tint and a partner tint one step round the
 * colour wheel: lav/iris, sky/teal, sage/moss, rose/berry, plum/orchid, stone/amber. An original
 * takes the next slot of `SLOT_BGS` in roster order: the six bases first (the design's lav, sky and
 * stone plus sage, rose and plum, so the first six keep the colours they always had), then the
 * partners. A twin takes its original's partner. So a pair still reads as a pair (F4 sky,
 * F4+Claude teal) and never shares a card, a tab or a line with anything else on the board.
 *
 * Partners are lent to originals from the last family backwards. A seventh original has to borrow
 * one, and the families at the top of the roster are the ones the owner has read longest, so they
 * keep their natural pair the longest. A twin whose partner an original already holds takes the
 * first free slot instead (see `looks`).
 *
 * Butter is not in the palette: it is the checklist's own sheet on mobile, and the month-by-month
 * sheet stacked right under it takes the picked strategy's tint, so a butter strategy would merge
 * them. Stone, the closest tint to the plain sheet in dark mode, is the last base. The partners were
 * picked in OKLab so that no two of the twelve sit closer than the two closest original tints
 * already did, and each is a step darker (light theme) or lighter (dark theme) than its base, so a
 * pair differs in lightness as well as in hue.
 *
 * Each sheet has its chart line in the same colour family (`--<tint>-line`, at least 3:1 against
 * the plain chart sheet in both themes; view.test.ts reads globals.css and holds that), so a card,
 * its tab and its curve all say the same colour.
 *
 * The roster is variable length, so the palette may not be assumed to cover it. Twelve research
 * strategies fill it. The thirteenth starts a second lap that reuses the sheets with a dashed line,
 * so lines stay unique for `LOOK_PERIOD` claims; past that both repeat. Every token is defined for
 * light and dark in `globals.css`.
 */
export const CARD_BGS = ['bg-lav', 'bg-sky', 'bg-sage', 'bg-rose', 'bg-plum', 'bg-stone'] as const;

/** Each family's partner sheet, at the same index as its base in `CARD_BGS`. */
export const PARTNER_BGS = ['bg-iris', 'bg-teal', 'bg-moss', 'bg-berry', 'bg-orchid', 'bg-amber'] as const;

/** The order originals take sheets in: the six bases, then the partners, last family first. */
export const SLOT_BGS = [...CARD_BGS, 'bg-amber', 'bg-orchid', 'bg-berry', 'bg-moss', 'bg-teal', 'bg-iris'] as const;

/** Research strategies before any sheet repeats. */
export const PALETTE_SIZE = SLOT_BGS.length;

/** Stroke patterns per lap of the palette: solid, then dashed. SPY's dotted '1 4' is not among them. */
export const LAP_DASHES = [null, '7 5'] as const;

/**
 * A Claude twin's stroke, by the lap of the sheet it holds: short even dashes, then dash-dot.
 * Neither is a lap dash or SPY's dotted '1 4', so a twin's line never equals an original's even
 * where a later lap reuses its colour. With the partner colour, the pair reads as "this one's pair,
 * with Claude" even on a glance at the legend.
 */
export const TWIN_DASHES = ['3 3', '10 3 2 3'] as const;

/** Sheet claims, originals and twins together, before any line repeats. */
export const LOOK_PERIOD = PALETTE_SIZE * LAP_DASHES.length;

/**
 * `bg` is the sheet class; `tint` is the same colour as a CSS value, for surfaces that borrow it;
 * `dash` is the line's stroke-dasharray, null for a solid line.
 */
export type Look = { bg: string; tint: string; line: string; width: number; dash: string | null };

/** 'bg-lav' -> 'lav': every sheet class in globals.css is a one-token background. */
const tokenOf = (bg: string): string => bg.slice(3);

/** One claim on the palette: which tint, on which lap of it. */
type Slot = { token: string; lap: number };

/** The n-th claim in `SLOT_BGS` order, laps included. */
const slotAt = (n: number): Slot => ({ token: tokenOf(SLOT_BGS[n % PALETTE_SIZE]), lap: Math.floor(n / PALETTE_SIZE) });

/** 'sky' -> 'teal' and 'teal' -> 'sky': a pair is a pair from either side. */
const PARTNER = new Map<string, string>(
  CARD_BGS.flatMap((bg, i): [string, string][] => [
    [tokenOf(bg), tokenOf(PARTNER_BGS[i])],
    [tokenOf(PARTNER_BGS[i]), tokenOf(bg)],
  ]),
);

export const LOOK_FALLBACK: Look = { bg: 'bg-sheet', tint: 'var(--sheet)', line: 'var(--ink-2)', width: 2, dash: null };

/** SPY's stroke: the benchmark is the dotted line on a plain sheet. */
export const BENCHMARK_DASH = '1 4';

/**
 * Card sheet and chart line per strategy id, by roster order, in three passes so that no
 * original's look can depend on a twin:
 *
 * 1. SPY gets the plain sheet and the dotted line. Each original (every row that is not an
 *    attached twin, a twin whose original is absent included) takes the first free slot of
 *    `SLOT_BGS` with its lap's dash, which on the live board is `SLOT_BGS[i]` for the i-th. Twins
 *    are not counted, so adding one moves no original: the owner keeps reading F1 as sage and C as
 *    rose.
 * 2. Each attached twin takes its original's partner, on its original's lap, when nothing holds it
 *    yet, with a `TWIN_DASHES` stroke and the ordinary width (a twin is never champion). That
 *    depends only on the original, so it does not depend on where the twin sits in `roster`.
 * 3. A twin whose partner is held (an original borrowed it, or the original has a second twin)
 *    takes the first free slot from its original's lap on. Up to `PALETTE_SIZE` research
 *    strategies there is always one on the first lap, so no two of them share a sheet, a tint or a
 *    line colour.
 *
 * The live board runs all three passes before any retired family (a retired original and its
 * twins) claims anything. The board carries its retired shelf, and past `PALETTE_SIZE` something
 * has to repeat; it must be a folded shelf card, never two live cards. MEASURED 2026-11-10 on the
 * real board: four live originals, three twins and six retired originals are 13 claims, and in
 * one roster-order pass the retired originals took moss and berry, so A+Claude fell to C's lav.
 */
export function looks(roster: (RosterIn & { status?: string })[]): Map<string, Look> {
  const out = new Map<string, Look>();
  const byId = new Map(roster.map(st => [st.id, st]));
  const originalOf = (st: RosterIn): RosterIn | null => {
    if (st.isBenchmark) return null;
    const o = attachedOriginal(st, byId);
    return o && !o.isBenchmark ? o : null;
  };
  const held = new Set<string>();
  const slotOf = new Map<string, Slot>();
  const keyOf = (s: Slot): string => `${s.token}|${s.lap}`;
  const freeFrom = (n: number): Slot => {
    while (held.has(keyOf(slotAt(n)))) n += 1;
    return slotAt(n);
  };
  const claim = (st: RosterIn, s: Slot, dash: string | null, width: number): void => {
    held.add(keyOf(s));
    slotOf.set(st.id, s);
    out.set(st.id, { bg: `bg-${s.token}`, tint: `var(--${s.token})`, line: `var(--${s.token}-line)`, width, dash });
  };

  const run = (rows: RosterIn[]): void => {
    for (const st of rows) {
      if (st.isBenchmark) {
        out.set(st.id, { bg: 'bg-sheet', tint: 'var(--sheet)', line: 'var(--ink-3)', width: 1.75, dash: BENCHMARK_DASH });
        continue;
      }
      if (originalOf(st)) continue;
      const s = freeFrom(0);
      claim(st, s, LAP_DASHES[s.lap % LAP_DASHES.length], st.isChampion ? 2.75 : 2);
    }

    const twins = rows.flatMap(st => {
      const o = originalOf(st);
      const at = o ? slotOf.get(o.id) : undefined;
      return at ? [{ st, at }] : [];
    });
    const displaced: typeof twins = [];
    for (const t of twins) {
      const want: Slot = { token: PARTNER.get(t.at.token) ?? t.at.token, lap: t.at.lap };
      if (held.has(keyOf(want))) displaced.push(t);
      else claim(t.st, want, TWIN_DASHES[want.lap % TWIN_DASHES.length], 2);
    }
    for (const t of displaced) {
      const s = freeFrom(t.at.lap * PALETTE_SIZE);
      claim(t.st, s, TWIN_DASHES[s.lap % TWIN_DASHES.length], 2);
    }
  };
  // A family is retired when its original is: a twin always claims in its original's pass.
  const retired = (st: RosterIn & { status?: string }): boolean =>
    ((originalOf(st) ?? st) as { status?: string }).status === 'retired';
  run(roster.filter(st => !retired(st)));
  run(roster.filter(retired));
  return out;
}

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

/**
 * How many rules the score divides by: `lib/metrics.ts`'s `CHECKLIST_RULES`, never a literal.
 *
 * The old comment here said "§1's five rules plus Backtest gate passed", which is the fossil that
 * produced the bug: that was true before design §13 (2026-10-07), when §1 had five forward clauses
 * and the gate made six. Today §1 has five conditions and the backtest gate IS the fifth of them.
 */
export const CHECKS = CHECKLIST_RULES;

/**
 * 'five' for 5. Small on purpose — the verdict lines name the rule count in words, and words that
 * are typed rather than derived are what outlived §13 here. Past the lookup it falls back to the
 * digits, which reads oddly but can never be wrong.
 */
const NUMBER_WORDS = ['no', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten'];
const numberWord = (n: number): string => NUMBER_WORDS[n] ?? String(n);

/** 'all five', continuing a line; and 'All five', leading one. */
const ALL = `all ${numberWord(CHECKS)}`;
const ALL_CAP = `${ALL[0].toUpperCase()}${ALL.slice(1)}`;

export type Score = { passed: number; total: number; ready: boolean; lines: [string, string] };

/**
 * The gate fields the score reads (a structural subset of lib/strategy's Gate). `twin?: true`,
 * exactly as `Gate`, so a GateIn still passes where `checklist` wants a Gate.
 */
export type GateIn = { passed: boolean; applicable: boolean; twin?: true };

/** A strategy with no checklist yet: not passed, applicable. */
export const NO_GATE: GateIn = { passed: false, applicable: true };

/**
 * The checklist score and its two-line verdict. Never "Ready for real money" unless every rule
 * passes, and never for a strategy whose backtest item is not applicable (C, handover D9, or a
 * Claude twin): real money for it would need an explicit owner decision even if the four forward
 * rules pass. A twin's lines say why its backtest cannot run, in the owner's words (brief §4.1):
 * Claude already knows how the past turned out.
 *
 * `items.length === CHECKS` is load-bearing and stays. `page.tsx` passes `items = []` for a
 * strategy with no gate row at all; a denominator of `items.length` would render that as 0/0 and
 * let a missing checklist read like a passing one. A fixed denominator makes it 0/5, "Paper only".
 */
export function scoreOf(items: { ok: boolean }[], gate: GateIn): Score {
  const passed = items.filter(i => i.ok).length;
  const ready = !gate.twin && gate.applicable && items.length === CHECKS && passed === CHECKS;
  const lines: [string, string] = gate.twin
    ? ['Paper only. No backtest possible.', 'Claude knows how the past turned out']
    : !gate.applicable
      ? ['Paper only. No backtest gate.', 'Real money needs an owner decision']
      : ready
        ? [`${ALL_CAP} pass.`, 'Ready for real money']
        : gate.passed
          ? ['Paper trading until', `${ALL} pass`]
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

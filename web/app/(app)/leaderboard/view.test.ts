import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { checklist, type Metrics, type Snapshot } from '../../../lib/metrics';
import type { MonthlyTable } from '../../../lib/monthly';
import {
  CARD_BGS, CHECKS, compare, LOOK_PERIOD, looks, MIN_COMMON_SESSIONS, MIN_RANKED, monthLabel, monthLines,
  NO_GATE, PALETTE_SIZE, PARTNER_BGS, pickResearch, researchOf, retiredLabel, scoreOf, sinceStartLine,
  SLOT_BGS, spyOverSpan, TWIN_DASHES, windowLine, type GateIn, type RankIn, type RosterIn,
} from './view';

const roster: RosterIn[] = [
  { id: 'SPY', isChampion: true, isBenchmark: true },
  { id: 'A', isChampion: false, isBenchmark: false },
  { id: 'F4-MOM12-N20-TREND', isChampion: false, isBenchmark: false },
  { id: 'F1-SPY-SMA200-M', isChampion: false, isBenchmark: false },
  { id: 'C', isChampion: false, isBenchmark: false },
];
const RESEARCH = ['A', 'F4-MOM12-N20-TREND', 'F1-SPY-SMA200-M', 'C'];

const research = (n: number, prefix = 'S'): RosterIn[] =>
  Array.from({ length: n }, (_, i) => ({ id: `${prefix}${i}`, isChampion: false, isBenchmark: false }));
const twinOf = (o: RosterIn): RosterIn => ({ id: `${o.id}-CX`, isChampion: false, isBenchmark: false, twinOf: o.id });

describe('looks', () => {
  it('gives the benchmark the dotted line on a plain sheet', () => {
    expect(looks(roster).get('SPY')).toEqual({ bg: 'bg-sheet', tint: 'var(--sheet)', line: 'var(--ink-3)', width: 1.75, dash: '1 4' });
  });
  it('assigns research sheets, and lines of the same colour, in roster order', () => {
    const l = looks(roster);
    expect(RESEARCH.map(id => l.get(id)!.bg)).toEqual(['bg-lav', 'bg-sky', 'bg-sage', 'bg-rose']);
    expect(RESEARCH.map(id => l.get(id)!.tint)).toEqual(['var(--lav)', 'var(--sky)', 'var(--sage)', 'var(--rose)']);
    expect(RESEARCH.map(id => l.get(id)!.line)).toEqual(['var(--lav-line)', 'var(--sky-line)', 'var(--sage-line)', 'var(--rose-line)']);
    expect(RESEARCH.map(id => l.get(id)!.width)).toEqual([2, 2, 2, 2]);
    expect(RESEARCH.map(id => l.get(id)!.dash)).toEqual([null, null, null, null]);
  });
  it('never gives C the look of A', () => {
    const l = looks(roster);
    expect(l.get('C')).not.toEqual(l.get('A'));
    expect(l.get('C')).toEqual({ bg: 'bg-rose', tint: 'var(--rose)', line: 'var(--rose-line)', width: 2, dash: null });
  });
  it('follows roster order, not ids', () => {
    const l = looks([roster[3], roster[0], roster[1]]);
    expect(l.get('F1-SPY-SMA200-M')!.bg).toBe('bg-lav');
    expect(l.get('A')!.bg).toBe('bg-sky');
  });
  it('gives six research strategies six different sheets, butter never among them', () => {
    const extra = ['X9', 'X10'].map(id => ({ id, isChampion: false, isBenchmark: false }));
    const l = looks([...roster, ...extra]);
    const bgs = [...RESEARCH, ...extra.map(e => e.id)].map(id => l.get(id)!.bg);
    expect(new Set(bgs).size).toBe(6);
    expect(bgs).not.toContain('bg-butter');
    expect(bgs).not.toContain('bg-sheet');
    expect(l.get('X9')).toEqual({ bg: 'bg-plum', tint: 'var(--plum)', line: 'var(--plum-line)', width: 2, dash: null });
    expect(l.get('X10')).toEqual({ bg: 'bg-stone', tint: 'var(--stone)', line: 'var(--stone-line)', width: 2, dash: null });
  });
  it('lends the seventh to twelfth originals the partners, last family first, before any dashed lap', () => {
    const l = looks(research(13));
    expect(l.get('S6')).toEqual({ bg: 'bg-amber', tint: 'var(--amber)', line: 'var(--amber-line)', width: 2, dash: null });
    expect(['S6', 'S7', 'S8', 'S9', 'S10', 'S11'].map(id => l.get(id)!.bg))
      .toEqual(['bg-amber', 'bg-orchid', 'bg-berry', 'bg-moss', 'bg-teal', 'bg-iris']);
    expect(l.get('S12')).toEqual({ bg: 'bg-lav', tint: 'var(--lav)', line: 'var(--lav-line)', width: 2, dash: '7 5' });
  });
  it('never gives two research strategies the same sheet up to PALETTE_SIZE, or the same line up to LOOK_PERIOD', () => {
    expect(PALETTE_SIZE).toBe(12);
    expect(LOOK_PERIOD).toBe(24);
    const many = research(LOOK_PERIOD);
    const l = looks(many);
    expect(new Set(many.slice(0, PALETTE_SIZE).map(st => l.get(st.id)!.bg)).size).toBe(PALETTE_SIZE);
    expect(new Set(many.map(st => `${l.get(st.id)!.line}|${l.get(st.id)!.dash}`)).size).toBe(LOOK_PERIOD);
  });
  it('emphasises a non-benchmark champion', () => {
    const l = looks([{ ...roster[0], isChampion: false }, { ...roster[1], isChampion: true }]);
    expect(l.get('A')!.width).toBe(2.75);
  });

  // Seer Adversarial + R1: a Claude twin wears its original's PARTNER colour with a twin dash. It
  // takes no original's slot, so every original keeps the colour it had before twins existed.
  const F4_TWIN: RosterIn = { id: 'F4-MOM12-N20-TREND-CX', isChampion: false, isBenchmark: false, twinOf: 'F4-MOM12-N20-TREND' };
  const withTwin: RosterIn[] = [roster[0], roster[1], roster[2], F4_TWIN, roster[3], roster[4]];

  it("gives a twin its original's partner sheet, tint and line, with a twin dash", () => {
    const l = looks(withTwin);
    expect(l.get('F4-MOM12-N20-TREND')).toEqual({ bg: 'bg-sky', tint: 'var(--sky)', line: 'var(--sky-line)', width: 2, dash: null });
    expect(l.get(F4_TWIN.id)).toEqual({ bg: 'bg-teal', tint: 'var(--teal)', line: 'var(--teal-line)', width: 2, dash: TWIN_DASHES[0] });
  });
  it('pairs every family with its own partner', () => {
    const originals = research(6);
    const twins = originals.map(twinOf);
    const l = looks([roster[0], ...originals, ...twins]);
    expect(originals.map(o => l.get(o.id)!.bg)).toEqual([...CARD_BGS]);
    expect(twins.map(t => l.get(t.id)!.bg)).toEqual([...PARTNER_BGS]);
  });
  it('moves no other strategy: originals keep their looks', () => {
    const before = looks(roster), after = looks(withTwin);
    for (const id of RESEARCH) expect(after.get(id)).toEqual(before.get(id));
    expect(after.get('SPY')).toEqual(before.get('SPY'));
  });
  it('moves no original, whichever original gains a twin, up to a full palette', () => {
    for (let n = 1; n <= PALETTE_SIZE; n++) {
      const originals = research(n);
      const before = looks([roster[0], ...originals]);
      for (const o of originals) {
        const after = looks([roster[0], ...originals, twinOf(o)]);
        for (const p of originals) expect(after.get(p.id)).toEqual(before.get(p.id));
      }
    }
  });
  it('gives every research strategy its own sheet and line colour, twins included, up to PALETTE_SIZE', () => {
    for (let n = 1; n <= PALETTE_SIZE; n++) {
      const originals = research(n);
      const t = Math.min(n, PALETTE_SIZE - n);
      // Twins of the first originals (natural partners), then of the last (the most displaced).
      for (const paired of [originals.slice(0, t), originals.slice(n - t)]) {
        const all = [...originals, ...paired.map(twinOf)];
        const l = looks([roster[0], ...all]);
        const bgs = all.map(st => l.get(st.id)!.bg);
        expect(new Set(bgs).size).toBe(all.length);
        expect(new Set(all.map(st => l.get(st.id)!.line)).size).toBe(all.length);
        expect(bgs).not.toContain('bg-butter');
        expect(bgs).not.toContain('bg-sheet');
      }
    }
  });
  it('lends a displaced twin the first free sheet', () => {
    // Seven originals: S6 borrows stone's partner (amber), so stone's twin takes the next free one.
    const originals = research(7);
    const l = looks([...originals, twinOf(originals[5])]);
    expect(l.get('S6')!.bg).toBe('bg-amber');
    expect(l.get('S5-CX')).toEqual({ bg: 'bg-orchid', tint: 'var(--orchid)', line: 'var(--orchid-line)', width: 2, dash: TWIN_DASHES[0] });
  });
  it('does not depend on where the twin sits in the roster', () => {
    const first = looks([F4_TWIN, ...roster]);
    expect(first.get(F4_TWIN.id)).toEqual(looks(withTwin).get(F4_TWIN.id));
    expect(first.get('A')!.bg).toBe('bg-lav');
  });
  it('colours a twin whose original is not on the roster like any other strategy', () => {
    const l = looks([roster[0], { id: 'X-CX', isChampion: false, isBenchmark: false, twinOf: 'X' }]);
    expect(l.get('X-CX')).toEqual({ bg: 'bg-lav', tint: 'var(--lav)', line: 'var(--lav-line)', width: 2, dash: null });
  });
  it("never emphasises a twin, even when its original is champion", () => {
    const l = looks([{ ...roster[1], isChampion: true }, { id: 'A-CX', isChampion: false, isBenchmark: false, twinOf: 'A' }]);
    expect(l.get('A')!.width).toBe(2.75);
    expect(l.get('A-CX')!.width).toBe(2);
  });
  it('never gives a twin the line of any original or of SPY, up to PALETTE_SIZE originals each with a twin', () => {
    const originals = research(PALETTE_SIZE);
    const twins = originals.map(twinOf);
    const l = looks([roster[0], ...originals, ...twins]);
    const all = [...originals, ...twins].map(st => `${l.get(st.id)!.line}|${l.get(st.id)!.dash}`);
    expect(new Set(all).size).toBe(LOOK_PERIOD);
    // Twelve originals hold every first-lap sheet, so every twin is lent one on the second lap.
    expect(l.get('S0-CX')!.dash).toBe(TWIN_DASHES[1]);
    for (const t of twins) expect(TWIN_DASHES as readonly string[]).toContain(l.get(t.id)!.dash);
  });
  it('gives every live card its own sheet before the retired shelf claims any, past PALETTE_SIZE', () => {
    // The real board on 2026-11-10: four live originals, three twins, six retired originals (13).
    const live = ['C', 'COSK', 'RAW35', 'A'].map(id => ({ id, isChampion: false, isBenchmark: false, status: 'active' }));
    const liveTwins = ['COSK', 'RAW35', 'A'].map(id => ({ ...twinOf({ id, isChampion: false, isBenchmark: false }), status: 'active' }));
    const shelf = ['RAW', 'MOM', 'MVW', 'RMW', 'FULL50', 'MOM70'].map(id => ({ id, isChampion: false, isBenchmark: false, status: 'retired' }));
    const board = [{ ...roster[0], status: 'active' }, live[0], live[1], liveTwins[0], live[2], liveTwins[1], live[3], liveTwins[2], ...shelf];
    const l = looks(board);
    expect(['C', 'COSK', 'COSK-CX', 'RAW35', 'RAW35-CX', 'A', 'A-CX'].map(id => l.get(id)!.bg))
      .toEqual(['bg-lav', 'bg-sky', 'bg-teal', 'bg-sage', 'bg-moss', 'bg-rose', 'bg-berry']);
    // Only the thirteenth claim repeats a sheet, and it is a folded shelf card on a dashed lap.
    expect(shelf.map(st => l.get(st.id)!.bg)).toEqual(['bg-plum', 'bg-stone', 'bg-amber', 'bg-orchid', 'bg-iris', 'bg-lav']);
    expect(l.get('MOM70')!.dash).toBe('7 5');
    // With no status the order is the plain roster-order rule, unchanged.
    expect(looks(board.map(({ status: _, ...st }) => st)).get('A-CX')!.bg).toBe('bg-lav');
  });
  it('keeps a retired twin in its retired original\'s pass', () => {
    const l = looks([
      { id: 'X', isChampion: false, isBenchmark: false, status: 'active' },
      { id: 'OLD', isChampion: false, isBenchmark: false, status: 'retired' },
      { id: 'OLD-CX', isChampion: false, isBenchmark: false, twinOf: 'OLD', status: 'active' },
    ]);
    expect([l.get('X')!.bg, l.get('OLD')!.bg, l.get('OLD-CX')!.bg]).toEqual(['bg-lav', 'bg-sky', 'bg-teal']);
  });
});

describe('palette tokens in globals.css', () => {
  const css = readFileSync(join(import.meta.dirname, '../../globals.css'), 'utf8');
  const light = css.match(/^:root \{([^}]*)\}/m)?.[1] ?? '';
  const dark = css.match(/@media \(prefers-color-scheme: dark\) \{\s*:root \{([^}]*)\}/)?.[1] ?? '';
  const token = (block: string, name: string): string | null =>
    block.match(new RegExp(`--${name}:\\s*(#[0-9a-fA-F]{6});`))?.[1] ?? null;
  const luminance = (hex: string): number => {
    const [r, g, b] = [1, 3, 5]
      .map(i => parseInt(hex.slice(i, i + 2), 16) / 255)
      .map(c => (c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const contrast = (a: string, b: string): number => {
    const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
    return (hi + 0.05) / (lo + 0.05);
  };

  it('finds both theme blocks', () => {
    expect(token(light, 'sheet')).toBe('#ffffff');
    expect(token(dark, 'sheet')).toBe('#211f1c');
  });
  it('defines every palette sheet and line for light and dark, with a sheet class', () => {
    for (const bg of SLOT_BGS) {
      const t = bg.slice(3);
      for (const block of [light, dark]) {
        expect(token(block, t), `--${t}`).not.toBeNull();
        expect(token(block, `${t}-line`), `--${t}-line`).not.toBeNull();
      }
      expect(css).toContain(`.${bg} { background: var(--${t}); }`);
    }
  });
  it('keeps every chart line at 3:1 or better against the plain chart sheet, in both themes', () => {
    for (const block of [light, dark]) {
      const sheet = token(block, 'sheet')!;
      for (const bg of SLOT_BGS) {
        const line = token(block, `${bg.slice(3)}-line`)!;
        expect(contrast(line, sheet), `${bg} line ${line} on ${sheet}`).toBeGreaterThanOrEqual(3);
      }
    }
  });
  it('keeps butter out of a palette of twelve different sheets', () => {
    expect(SLOT_BGS as readonly string[]).not.toContain('bg-butter');
    expect(new Set(SLOT_BGS).size).toBe(12);
  });
});

describe('researchOf', () => {
  it('lists research strategies only', () => {
    expect(researchOf(roster).map(s => s.id)).toEqual(RESEARCH);
  });
});

// --- the common-window comparison (R3, invariant 6) ---------------------------------------------

/** `n` consecutive dates from `start`. compare() reads dates, not a calendar: weekends do not matter. */
function days(start: string, n: number): string[] {
  const t0 = Date.parse(`${start}T00:00:00Z`);
  return Array.from({ length: n }, (_, i) => new Date(t0 + i * 86_400_000).toISOString().slice(0, 10));
}
const curveOf = (start: string, equities: number[]): Snapshot[] =>
  days(start, equities.length).map((date, i) => ({ date, equity: equities[i] }));
/** 100000 on every date but the last, so the window's total return is exactly `ret`. */
const flatThen = (n: number, ret: number) => [...Array(n - 1).fill(100000), 100000 * (1 + ret)];

const st = (id: string, status: 'active' | 'retired' = 'active'): RankIn =>
  ({ id, isChampion: false, isBenchmark: false, status });
const bench: RankIn = { id: 'SPY', isChampion: true, isBenchmark: true, status: 'active' };

// Shared window: 2026-03-02 .. 2026-05-03, 63 sessions — exactly MIN_COMMON_SESSIONS, so every
// fixture here is the smallest board that can be ranked at all.
const SHARED = '2026-03-02';
const N = MIN_COMMON_SESSIONS;        // 63
const A1 = { strategy: st('A1'), curve: curveOf(SHARED, flatThen(N, 0.01)) };
const B1 = { strategy: st('B1'), curve: curveOf(SHARED, flatThen(N, 0.005)) };
// Doubled its money before the window opened; inside it, it made 0.2%. Raw total return would
// crown it; the common window must not.
const OLD = {
  strategy: st('OLD'),
  curve: curveOf('2026-01-31', [...Array(30).fill(50000), ...flatThen(N, 0.002)]),
};
const SPY_ROW = { strategy: bench, curve: curveOf(SHARED, flatThen(N, 0.9)) };

describe('compare', () => {
  it('ranks over the sessions every compared strategy shares, and reports that window', () => {
    const c = compare([SPY_ROW, A1, B1, OLD]);
    expect(c.window).toEqual({ from: '2026-03-02', to: '2026-05-03', sessions: 63 });
    expect(c.ranked.map(r => r.strategy.id)).toEqual(['A1', 'B1', 'OLD']);
    expect(c.best?.strategy.id).toBe('A1');
    expect(c.best?.totalReturn).toBeCloseTo(0.01, 10);
    expect(c.best?.sessions).toBe(63);

    // Every figure below is `as_json(compare(...))` from seer_engine/paper/compare.py on these
    // very fixtures, not a hand-computed expectation: the port is pinned against the reference
    // implementation, which is the one failure mode a port has that a call does not.
    //   totalReturn, cagr, maxDrawdown, sharpe, inception
    const PY: Record<string, [number, number, number, number, number]> = {
      A1: [0.01, 0.0603708262, 0, 2.0160645150967413, 0.01],
      B1: [0.005, 0.0298181679, 0, 2.0160645150967413, 0.005],
      OLD: [0.002, 0.0118400363, 0, 2.0160645150967413, 1.004],
    };
    for (const r of c.ranked) {
      const [tr, cagr, dd, sharpe, inception] = PY[r.strategy.id];
      expect(r.totalReturn!).toBeCloseTo(tr, 12);
      expect(r.cagr!).toBeCloseTo(cagr, 9);
      expect(r.maxDrawdown!).toBeCloseTo(dd, 12);
      expect(r.sharpe!).toBeCloseTo(sharpe, 12);
      expect(r.inception!).toBeCloseTo(inception, 12);
    }
    // All three curves have the same shape, so Sharpe ties and the rank falls through to total
    // return descending — Python ranks them 1/2/3 in exactly this order for exactly that reason.
    expect(new Set(c.ranked.map(r => r.sharpe)).size).toBe(1);
  });

  it('is the engine module’s minimum, not its own', () => {
    // The one number that must never drift from seer_engine/paper/compare.py.
    expect(MIN_COMMON_SESSIONS).toBe(63);
    expect(MIN_RANKED).toBe(2);
  });

  it('drops the worst-overlapping strategy rather than ranking nothing', () => {
    // compare.py's `_select`: ODD overlaps the others by only 20 sessions, so including it would
    // leave the board below 63. It goes; the other three still rank over their own 63.
    const odd = { strategy: st('ODD'), curve: curveOf('2026-04-14', flatThen(80, 0.4)) };
    const c = compare([A1, B1, OLD, odd]);
    expect(c.window).toEqual({ from: '2026-03-02', to: '2026-05-03', sessions: 63 });
    expect(c.ranked.map(r => r.strategy.id)).toEqual(['A1', 'B1', 'OLD']);
    expect(c.rows.find(r => r.strategy.id === 'ODD')!.status).toBe('insufficient');
    expect(c.best!.strategy.id).toBe('A1'); // +40% but unranked: it does not win
  });

  it('does not depend on the order the rows arrive in', () => {
    const base = compare([A1, B1, OLD]);
    const shuffled = compare([OLD, B1, A1]);
    expect(shuffled.ranked.map(r => r.strategy.id)).toEqual(base.ranked.map(r => r.strategy.id));
    expect(shuffled.window).toEqual(base.window);
  });

  it('does not crown a return earned outside the window (what bestResearch got wrong)', () => {
    const c = compare([A1, B1, OLD]);
    const old = c.rows.find(r => r.strategy.id === 'OLD')!;
    expect(old.inception).toBeCloseTo(100200 / 50000 - 1, 10); // +100.4% inception to date
    expect(old.totalReturn).toBeCloseTo(0.002, 10);            // +0.2% over the shared window
    expect(c.best!.strategy.id).toBe('A1');                    // raw max would have said OLD
    expect(c.best!.totalReturn!).toBeLessThan(old.inception!);
  });

  it('never compares the benchmark', () => {
    const c = compare([SPY_ROW, A1, B1]);
    expect(c.rows.map(r => r.strategy.id)).toEqual(['A1', 'B1']);
  });

  it('calls a newcomer insufficient without letting it shorten the others’ window', () => {
    const fresh = { strategy: st('NEW'), curve: curveOf('2026-04-20', flatThen(9, 0.05)) };
    const c = compare([A1, B1, OLD, fresh]);
    expect(c.window).toEqual({ from: '2026-03-02', to: '2026-05-03', sessions: 63 });
    const n = c.rows.find(r => r.strategy.id === 'NEW')!;
    expect(n.status).toBe('insufficient');
    expect(n.sessions).toBe(9);
    expect(c.ranked.map(r => r.strategy.id)).toEqual(['A1', 'B1', 'OLD']);
    expect(c.best!.strategy.id).toBe('A1'); // +5% but unranked: it does not win
  });

  it('keeps a retired strategy’s record, out of the ranking and out of the window', () => {
    const gone = { strategy: st('GONE', 'retired'), curve: curveOf(SHARED, flatThen(N, 0.2)) };
    const c = compare([A1, B1, OLD, gone]);
    const g = c.rows.find(r => r.strategy.id === 'GONE')!;
    expect(g.status).toBe('retired');
    expect(g.inception).toBeCloseTo(0.2, 10);     // the record stands
    expect(g.totalReturn).toBeNull();             // but it is not a ranking
    expect(c.ranked.map(r => r.strategy.id)).not.toContain('GONE');
    expect(c.best!.strategy.id).toBe('A1');       // +20% retired does not win
    expect(c.window).toEqual({ from: '2026-03-02', to: '2026-05-03', sessions: 63 });
  });

  it('ranks nothing while the common window is short, and still reports how short', () => {
    const short = MIN_COMMON_SESSIONS - 11;   // 52
    const c = compare([
      { strategy: st('A1'), curve: curveOf(SHARED, flatThen(short, 0.01)) },
      { strategy: st('B1'), curve: curveOf(SHARED, flatThen(short, 0.02)) },
    ]);
    expect(c.ranked).toEqual([]);
    expect(c.best).toBeNull();
    // `window` is null whenever nothing ranked — compare.py's own guarantee. How short the board
    // still is lives in `shared`, which is never a ranking.
    expect(c.window).toBeNull();
    expect(c.shared).toBe(short);
    expect(c.rows.map(r => r.status)).toEqual(['insufficient', 'insufficient']);
  });

  it('leaves every windowed figure null on any row it did not rank', () => {
    const gone = { strategy: st('GONE', 'retired'), curve: curveOf(SHARED, flatThen(N, 0.2)) };
    const fresh = { strategy: st('NEW'), curve: curveOf('2026-04-20', flatThen(9, 0.05)) };
    for (const r of compare([A1, B1, gone, fresh]).rows) {
      if (r.status === 'ranked') continue;
      expect([r.totalReturn, r.cagr, r.maxDrawdown, r.sharpe]).toEqual([null, null, null, null]);
    }
  });
});

describe('windowLine', () => {
  it('names the window the ranking used and how many strategies it covered', () => {
    const w = windowLine(compare([A1, B1, OLD]));
    expect(w.label).toBe('Ranked over Mar 2 – May 3');
    expect(w.detail).toBe('63 shared sessions · 3 of 3 active strategies compared');
  });
  it('says how far off a window is rather than showing an unearned ranking', () => {
    const short = MIN_COMMON_SESSIONS - 11;
    const w = windowLine(compare([
      { strategy: st('A1'), curve: curveOf(SHARED, flatThen(short, 0.01)) },
      { strategy: st('B1'), curve: curveOf(SHARED, flatThen(short, 0.02)) },
    ]));
    expect(w.label).toBe('No common window yet');
    expect(w.detail).toBe(`${short} of ${MIN_COMMON_SESSIONS} sessions shared by every strategy`);
  });
});

describe('spyOverSpan', () => {
  it('measures the benchmark over the strategy’s own span, not over its whole record', () => {
    // 30 days at 10, then 63 days rising 100 → 162. The pick spans exactly those 63 days.
    const spy = curveOf('2026-01-31', [...Array(30).fill(10), ...Array(N).fill(0).map((_, i) => 100 + i)]);
    const pick = curveOf(SHARED, flatThen(N, 0.01));
    expect(spyOverSpan(spy, pick)).toBeCloseTo(162 / 100 - 1, 10);
  });
  it('is null when the benchmark has no snapshot on a boundary date', () => {
    expect(spyOverSpan(curveOf('2026-06-01', flatThen(5, 0.1)), curveOf(SHARED, flatThen(N, 0.01)))).toBeNull();
    expect(spyOverSpan(curveOf(SHARED, flatThen(N, 0.01)), [{ date: SHARED, equity: 1 }])).toBeNull();
  });
});

describe('pickResearch', () => {
  const list = [st('GONE', 'retired'), st('A1'), st('B1')];
  it('defaults to the first active strategy, never to a retired one', () => {
    expect(pickResearch(list, undefined)?.id).toBe('A1');
    expect(pickResearch(list, 'nope')?.id).toBe('A1');
  });
  it('honours an explicit request for a retired strategy: the record stays reachable', () => {
    expect(pickResearch(list, 'GONE')?.id).toBe('GONE');
  });
  it('falls back to the first row when every strategy is retired, and is null when there are none', () => {
    expect(pickResearch([st('GONE', 'retired')], undefined)?.id).toBe('GONE');
    expect(pickResearch([], undefined)).toBeNull();
  });
});

describe('retiredLabel', () => {
  it('names the date it stopped, and degrades before paper_end is written', () => {
    expect(retiredLabel('2026-12-02')).toBe('Retired Dec 2');
    expect(retiredLabel(null)).toBe('Retired');
  });
});

describe('scoreOf', () => {
  const PASSED = { passed: true, applicable: true };
  const FAILED = { passed: false, applicable: true };
  const NOT_APPLICABLE = { passed: false, applicable: false };

  // Driven by the REAL `checklist()`, not by hand-built arrays. Hand-built fixtures are how the
  // 2026-10-07 drift got through: six-element arrays agreed with `CHECKS = 6` for ever while
  // production fed `scoreOf` five rows, so the suite stayed green over an unreachable `ready`.
  // Whatever the rule count becomes next, these cases are built from the list itself.
  const SPY = 0.046;
  /** Passes all four forward rules: 24 months ≥ 18, +6.8% beats SPY's +4.6%, PF 1.42, drawdown 7.9%. */
  const STRONG: Metrics = {
    totalReturn: 0.068, winRate: 0.58, profitFactor: 1.42, maxDrawdown: 0.079, trades: 84, months: 24,
  };
  /** Fails two of them: 3.0 months (< 18) and a 1.10 profit factor (< 1.3). */
  const WEAK: Metrics = { ...STRONG, months: 3.0, profitFactor: 1.1 };
  const checks = (m: Metrics, gate: GateIn) => checklist(m, SPY, gate);

  it('scores out of the rules the checklist returns, and says paper only while the gate has not passed', () => {
    const sc = scoreOf(checks(STRONG, FAILED), FAILED);
    expect(sc).toEqual({ passed: 4, total: CHECKS, ready: false, lines: ['Paper only.', 'Backtest gate not passed'] });
    // A strategy with no gate row at all: page.tsx passes []. It must read 0 of CHECKS, never 0/0.
    expect(scoreOf([], NO_GATE)).toEqual({
      passed: 0, total: CHECKS, ready: false, lines: ['Paper only.', 'Backtest gate not passed'],
    });
  });

  it('says paper trading until all five pass when the gate passed but a forward rule did not', () => {
    const sc = scoreOf(checks(WEAK, PASSED), PASSED);
    expect(sc.passed).toBe(3);
    expect(sc.ready).toBe(false);
    expect(sc.lines).toEqual(['Paper trading until', 'all five pass']);
  });

  // THE regression pin for the reported bug. On `main` at d8c0cab this read 5 of 6, ready: false,
  // "Paper trading until / all six pass" — a strategy that passed every rule could never go live.
  it('is ready when all five pass with a passed gate', () => {
    const sc = scoreOf(checks(STRONG, PASSED), PASSED);
    expect(sc.ready).toBe(true);
    expect(sc.passed).toBe(5);
    expect(sc.total).toBe(5);
    expect(sc.lines).toEqual(['All five pass.', 'Ready for real money']);
  });

  // Replaces 'is never ready with fewer than six items', which asserted that five passing rules are
  // not ready — i.e. it pinned the bug, using production's own input as the counter-example. The
  // real invariant is this one: the number the score divides by IS the number of rows rendered.
  it('divides by the number of rows checklist actually returns', () => {
    expect(scoreOf(checks(STRONG, PASSED), PASSED).total).toBe(checks(STRONG, PASSED).length);
    expect(CHECKS).toBe(checks(STRONG, NOT_APPLICABLE).length);
  });

  it('says real money needs an owner decision when the gate is not applicable (C, handover D9)', () => {
    const sc = scoreOf(checks(STRONG, NOT_APPLICABLE), NOT_APPLICABLE);
    expect(sc).toEqual({
      passed: 4, total: CHECKS, ready: false,
      lines: ['Paper only. No backtest gate.', 'Real money needs an owner decision'],
    });
  });

  it('is never ready when the gate is not applicable, whatever the rules say', () => {
    const sc = scoreOf(checks(STRONG, NOT_APPLICABLE), NOT_APPLICABLE);
    expect(sc.ready).toBe(false);
    expect(sc.lines[1]).toBe('Real money needs an owner decision');
  });
  it("says a twin's backtest cannot be run, and why, and is never ready", () => {
    const TWIN = { passed: false, applicable: false, twin: true as const };
    const sc = scoreOf(checks(STRONG, TWIN), TWIN);
    expect(sc).toEqual({
      passed: 4, total: CHECKS, ready: false,
      lines: ['Paper only. No backtest possible.', 'Claude knows how the past turned out'],
    });
    // A malformed twin gate that claims a pass is still not ready.
    expect(scoreOf(checks(STRONG, PASSED), { passed: true, applicable: true, twin: true }).ready).toBe(false);
  });
});

describe('month rows', () => {
  // Phase 10's MonthlyTable shape, oldest first as monthly() returns it.
  const t: MonthlyTable = {
    months: [
      { month: '2026-10', from: '2026-10-05', to: '2026-10-30', return: 0.012, spyReturn: 0.008, trades: 3, worstDrop: 0.021, partial: true },
      { month: '2026-11', from: '2026-10-30', to: '2026-11-30', return: -0.004, spyReturn: null, trades: 0, worstDrop: 0, partial: false },
      { month: '2026-12', from: '2026-11-30', to: '2026-12-02', return: 0, spyReturn: 0.01, trades: 0, worstDrop: 0.005, partial: true },
    ],
    sinceStart: { from: '2026-10-05', to: '2026-12-02', return: 0.008, spyReturn: 0.019, trades: 3, worstDrop: 0.03 },
  };
  it('labels months', () => {
    expect(monthLabel('2026-10')).toBe('Oct 2026');
  });
  it('orders newest first and formats every column', () => {
    const rows = monthLines(t);
    expect(rows.map(r => r.key)).toEqual(['2026-12', '2026-11', '2026-10']);
    expect(rows[1]).toEqual({
      key: '2026-11', label: 'Nov 2026', partial: false,
      ret: { text: '−0.4%', tone: 'neg' }, spy: '—', trades: '0', drop: '0.0%',
    });
    expect(rows[2]).toEqual({
      key: '2026-10', label: 'Oct 2026', partial: true,
      ret: { text: '+1.2%', tone: 'pos' }, spy: '+0.8%', trades: '3', drop: '2.1%',
    });
    expect(rows[0].partial).toBe(true);
  });
  it('builds the since-start row from day 0', () => {
    expect(sinceStartLine(t)).toEqual({
      key: 'since-start', label: 'Since Oct 5', partial: false,
      ret: { text: '+0.8%', tone: 'pos' }, spy: '+1.9%', trades: '3', drop: '3.0%',
    });
  });
  it('has no since-start row before the first paper session', () => {
    expect(sinceStartLine({ months: [], sinceStart: null })).toBeNull();
  });
});


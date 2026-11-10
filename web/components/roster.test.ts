import { BookOpen, CloudLightning, Gauge, Gavel, Landmark, Rocket, Scale, Shield, Sigma, Zap } from 'lucide-react';
import { describe, expect, it } from 'vitest';
import {
  displayIcons, selectStrategy, sharesLabel, SPARE_ICONS, strategyIcon, TWIN_ICON, withDisplayIcons, type IconIn,
} from './roster';

const roster = [
  { id: 'SPY', name: 'SPY', isChampion: true, isBenchmark: true },
  { id: 'A', name: 'A · Quant', isChampion: false, isBenchmark: false },
  { id: 'F4-MOM12-N20-TREND', name: 'F4 · Momentum', isChampion: false, isBenchmark: false },
  { id: 'F1-SPY-SMA200-M', name: 'F1 · Trend', isChampion: false, isBenchmark: false },
  { id: 'C', name: 'C · News veto', isChampion: false, isBenchmark: false },
];

describe('selectStrategy', () => {
  it('returns the requested strategy when it is on the roster', () => {
    expect(selectStrategy(roster, 'F1-SPY-SMA200-M')?.id).toBe('F1-SPY-SMA200-M');
    expect(selectStrategy(roster, 'SPY')?.id).toBe('SPY');
    expect(selectStrategy(roster, 'C')?.id).toBe('C');
  });
  it('defaults to the first research strategy', () => {
    expect(selectStrategy(roster, undefined)?.id).toBe('A');
    expect(selectStrategy(roster, 'B')?.id).toBe('A');
  });
  it('falls back to the first row, then null', () => {
    expect(selectStrategy([roster[0]], undefined)?.id).toBe('SPY');
    expect(selectStrategy([], undefined)).toBeNull();
  });
});

describe('strategyIcon', () => {
  it('maps the roster icons and falls back to Sigma', () => {
    expect(strategyIcon('landmark')).toBe(Landmark);
    expect(strategyIcon('trending-up')).toBe(Gauge);
    expect(strategyIcon('shield')).toBe(Shield);
    expect(strategyIcon('gavel')).toBe(Gavel);
    expect(strategyIcon('sigma')).toBe(Sigma);
    expect(strategyIcon('book-open')).toBe(BookOpen);
    expect(strategyIcon('zap')).toBe(Zap);
    expect(strategyIcon('scale')).toBe(Scale);
    expect(strategyIcon('cloud-lightning')).toBe(CloudLightning);
    expect(strategyIcon('nope')).toBe(Sigma);
    expect(strategyIcon('constructor')).toBe(Sigma);
  });
  it('registers every twin partner and spare, each drawing its own icon, none a disabled-looking -off', () => {
    const extra = [...TWIN_ICON.values(), ...SPARE_ICONS];
    for (const name of extra) {
      expect(strategyIcon(name), name).not.toBe(Sigma);
      expect(name.endsWith('-off')).toBe(false);
    }
    const drawn = [...TWIN_ICON.keys(), ...extra].map(strategyIcon);
    expect(new Set(drawn).size).toBe(drawn.length);
  });
});

describe('sharesLabel', () => {
  it('formats whole and fractional shares', () => {
    expect(sharesLabel(1)).toBe('1 share');
    expect(sharesLabel(3)).toBe('3 shares');
    expect(sharesLabel(2.5)).toBe('2.5 shares');
    expect(sharesLabel(0.123456)).toBe('0.1235 shares');
  });
});

const row = (id: string, icon: string, extra: Partial<IconIn> = {}): IconIn => ({ id, icon, isBenchmark: false, twinOf: null, ...extra });
const SPY = row('SPY', 'landmark', { isBenchmark: true });

describe('displayIcons', () => {
  it('keeps every stored icon when none collide', () => {
    const r = [SPY, row('A', 'sigma'), row('F4', 'trending-up'), row('F1', 'shield'), row('C', 'gavel')];
    expect([...displayIcons(r)]).toEqual([['SPY', 'landmark'], ['A', 'sigma'], ['F4', 'trending-up'], ['F1', 'shield'], ['C', 'gavel']]);
  });
  it("gives a twin its original's partner icon", () => {
    const m = displayIcons([SPY, row('F4', 'trending-up'), row('F4-CX', 'trending-up', { twinOf: 'F4' })]);
    expect(m.get('F4')).toBe('trending-up');
    expect(m.get('F4-CX')).toBe('rocket');
    expect(strategyIcon(m.get('F4-CX')!)).toBe(Rocket);
  });
  it('resolves the board the owner reported (three originals with twins) to eight different icons', () => {
    // Roster order and stored icons from the 2026-11-10 analysis screenshot; ids shortened.
    const r = [
      SPY, row('C', 'gavel'),
      row('COSK', 'cloud-lightning'), row('COSK-CX', 'cloud-lightning', { twinOf: 'COSK' }),
      row('RAW35', 'zap'), row('RAW35-CX', 'zap', { twinOf: 'RAW35' }),
      row('A', 'sigma'), row('A-CX', 'sigma', { twinOf: 'A' }),
    ];
    const m = displayIcons(r);
    expect(r.map(st => m.get(st.id))).toEqual(['landmark', 'gavel', 'cloud-lightning', 'tornado', 'zap', 'flame', 'sigma', 'pi']);
  });
  it('keeps landmark for SPY even when a research row listed before it stores landmark', () => {
    const m = displayIcons([row('X', 'landmark'), SPY]);
    expect(m.get('SPY')).toBe('landmark');
    expect(m.get('X')).toBe(SPARE_ICONS[0]);
  });
  it('gives each later original that stores a taken icon the next spare', () => {
    const m = displayIcons([SPY, row('A', 'sigma'), row('B', 'sigma'), row('C', 'sigma')]);
    expect([m.get('A'), m.get('B'), m.get('C')]).toEqual(['sigma', SPARE_ICONS[0], SPARE_ICONS[1]]);
  });
  it('treats an unknown stored icon as the Sigma it draws', () => {
    const m = displayIcons([SPY, row('A', 'sigma'), row('B', 'nope')]);
    expect(m.get('B')).toBe(SPARE_ICONS[0]);
  });
  it('sends a twin to a spare when an original already holds its partner icon', () => {
    const m = displayIcons([SPY, row('F4', 'trending-up'), row('R', 'rocket'), row('F4-CX', 'trending-up', { twinOf: 'F4' })]);
    expect(m.get('R')).toBe('rocket');
    expect(m.get('F4-CX')).toBe(SPARE_ICONS[0]);
  });
  it('does not depend on where a twin sits relative to its original', () => {
    const after = displayIcons([SPY, row('F4', 'trending-up'), row('F4-CX', 'trending-up', { twinOf: 'F4' })]);
    const before = displayIcons([SPY, row('F4-CX', 'trending-up', { twinOf: 'F4' }), row('F4', 'trending-up')]);
    expect(before.get('F4')).toBe(after.get('F4'));
    expect(before.get('F4-CX')).toBe(after.get('F4-CX'));
  });
  it('resolves a list the same way when more rows follow it (strategies() vs boardStrategies())', () => {
    const live = [SPY, row('A', 'sigma'), row('A-CX', 'sigma', { twinOf: 'A' }), row('F4', 'trending-up')];
    const board = [...live, row('OLD', 'pi'), row('OLD-CX', 'pi', { twinOf: 'OLD' })];
    const a = displayIcons(live), b = displayIcons(board);
    for (const st of live) expect(b.get(st.id)).toBe(a.get(st.id));
    expect(b.get('OLD')).toBe(SPARE_ICONS[0]);
    expect(b.get('OLD-CX')).toBe(SPARE_ICONS[1]);
  });
  it('draws a different icon for every row of a twelve-strategy roster where every original has a twin', () => {
    const stored = [...TWIN_ICON.keys()].filter(n => n !== 'landmark').slice(0, 6);
    const all = [SPY, ...stored.flatMap((icon, i) => [row(`S${i}`, icon), row(`S${i}-CX`, icon, { twinOf: `S${i}` })])];
    const m = displayIcons(all);
    const drawn = all.map(st => strategyIcon(m.get(st.id)!));
    expect(new Set(drawn).size).toBe(all.length);
  });
  it('withDisplayIcons swaps only the icon, keeps the order and leaves the input alone', () => {
    const r = [SPY, row('F4', 'trending-up'), row('F4-CX', 'trending-up', { twinOf: 'F4' })];
    const out = withDisplayIcons(r);
    expect(out.map(st => st.id)).toEqual(['SPY', 'F4', 'F4-CX']);
    expect(out[2]).toEqual({ ...r[2], icon: 'rocket' });
    expect(r[2].icon).toBe('trending-up');
  });
});

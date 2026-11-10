import {
  Activity, Anchor, BookOpen, BrainCircuit, Building, CloudLightning, Compass, Cpu, Feather, Flame, Gauge, Gavel, Gem,
  Landmark, Leaf, Library, Mountain, Newspaper, Orbit, Pi, Puzzle, Radar, Rocket, Sailboat, Scale, Shield, Sigma,
  Tornado, Umbrella, Waypoints, Weight, Zap, type LucideIcon,
} from 'lucide-react';
import { attachedOriginal } from '../lib/strategy';

// The `icon` column of `strategies` names a Lucide icon (kebab-case). Roster: landmark (SPY),
// sigma (A), trending-up (F4), shield (F1), gavel (C, migration 004), book-open (FND), activity (RM, 010),
// zap (RAW, 013), scale (MVW, 013), cloud-lightning (COSK, 022: the stocks that fall hardest in the market's storms);
// brain-circuit kept for old demo rows.
// F4's stored 'trending-up' draws Gauge: History's "Wins only" filter already uses TrendingUp.
//
// The rest are display-only, never stored: each stored icon's twin partner (`TWIN_ICON`) and the
// spare pool (`SPARE_ICONS`) that `displayIcons` draws from when two rows would share an icon.
const ICONS: Record<string, LucideIcon> = {
  landmark: Landmark,
  sigma: Sigma,
  'trending-up': Gauge,
  shield: Shield,
  'brain-circuit': BrainCircuit,
  gavel: Gavel,
  'book-open': BookOpen,
  activity: Activity,
  zap: Zap,
  scale: Scale,
  'cloud-lightning': CloudLightning,
  building: Building,
  pi: Pi,
  rocket: Rocket,
  umbrella: Umbrella,
  cpu: Cpu,
  newspaper: Newspaper,
  library: Library,
  radar: Radar,
  flame: Flame,
  weight: Weight,
  tornado: Tornado,
  compass: Compass,
  anchor: Anchor,
  feather: Feather,
  gem: Gem,
  leaf: Leaf,
  mountain: Mountain,
  orbit: Orbit,
  puzzle: Puzzle,
  sailboat: Sailboat,
  waypoints: Waypoints,
};

/** The registered name a stored icon draws as: itself when registered, else 'sigma', the fallback. */
const drawnName = (name: string): string => (Object.prototype.hasOwnProperty.call(ICONS, name) ? name : 'sigma');

/** The Lucide icon a strategies row names; Sigma when the name is unknown. */
export const strategyIcon = (name: string): LucideIcon => ICONS[drawnName(name)];

/**
 * A Claude twin's icon, by its original's. The engine copies the original's `icon` onto the twin
 * row (`ensure_twins`), which made a pair indistinguishable in every icon row on the site. Each
 * partner keeps a family likeness so the pair still reads as a pair (sigma/pi, gavel/newspaper,
 * zap/flame, cloud-lightning/tornado) while drawing visibly differently at 19px. Display only: the
 * DB keeps what the engine wrote, so no migration and no engine change for a visual concern.
 */
export const TWIN_ICON: ReadonlyMap<string, string> = new Map([
  ['landmark', 'building'],
  ['sigma', 'pi'],
  ['trending-up', 'rocket'],
  ['shield', 'umbrella'],
  ['brain-circuit', 'cpu'],
  ['gavel', 'newspaper'],
  ['book-open', 'library'],
  ['activity', 'radar'],
  ['zap', 'flame'],
  ['scale', 'weight'],
  ['cloud-lightning', 'tornado'],
]);

/**
 * Where a row goes when the icon it wants is already on the board, in this order. None of them is
 * a stored icon, a twin partner, a `-off` icon (those read as "disabled"), or an icon the app uses
 * for something else (telescope is Sera's nav icon; target and hourglass are History's exits).
 */
export const SPARE_ICONS = [
  'compass', 'anchor', 'feather', 'gem', 'leaf', 'mountain', 'orbit', 'puzzle', 'sailboat', 'waypoints',
] as const;

/** The roster fields the resolver reads: a structural subset of lib/data's `Strategy`. */
export type IconIn = { id: string; icon: string; isBenchmark: boolean; twinOf?: string | null };

/**
 * One icon name per strategy id, unique across `roster` (R1: every method is unique in icon).
 *
 * The benchmark claims first, so SPY always keeps its landmark. Then each row, in roster order,
 * claims the icon it stores (an unknown name counts as the Sigma it draws), and an attached Claude
 * twin claims its original's partner (`TWIN_ICON`). A claim that is already taken gets the next
 * free `SPARE_ICONS` entry. Only if all of those are gone too does it keep what it wanted.
 *
 * Every screen passes the roster it already has. Claims run in roster order, so a list resolves
 * the same way whatever rows follow it. `strategies()` is a prefix of `boardStrategies()`, which is
 * why Positions, History, Sean's plan and the Leaderboard agree on every live strategy's icon. A
 * twin listed before its original resolves the original first, so a twin's icon never depends on
 * where it sits.
 */
export function displayIcons(roster: IconIn[]): Map<string, string> {
  const out = new Map<string, string>();
  const taken = new Set<string>();
  const byId = new Map(roster.map(st => [st.id, st]));
  const claim = (st: IconIn, wanted: string): void => {
    const icon = !taken.has(wanted) ? wanted : (SPARE_ICONS.find(n => !taken.has(n)) ?? wanted);
    taken.add(icon);
    out.set(st.id, icon);
  };
  const resolve = (st: IconIn): void => {
    if (out.has(st.id)) return;
    const o = st.isBenchmark ? null : attachedOriginal(st, byId);
    if (!o || o.isBenchmark) {
      claim(st, drawnName(st.icon));
      return;
    }
    resolve(o);
    const mine = out.get(o.id) ?? drawnName(o.icon);
    claim(st, TWIN_ICON.get(mine) ?? mine);
  };
  for (const st of roster) if (st.isBenchmark) resolve(st);
  for (const st of roster) resolve(st);
  return out;
}

/** `roster` with each row's `icon` replaced by its `displayIcons` name; the input is not mutated. */
export function withDisplayIcons<T extends IconIn>(roster: T[]): T[] {
  const icons = displayIcons(roster);
  return roster.map(st => ({ ...st, icon: icons.get(st.id) ?? st.icon }));
}

// Short labels and the paper flag are phase 10's: `Strategy.short` (lib/strategy.ts `shortLabel`)
// and `Strategy.isPaper`. This module holds only what web/lib lacks.

/**
 * The strategy a screen shows: the requested id when it is on the roster, else the first
 * research (non-benchmark) strategy, else the first row, else null.
 */
export function selectStrategy<T extends { id: string; isBenchmark: boolean }>(
  roster: T[],
  requested: string | undefined,
): T | null {
  return roster.find(r => r.id === requested) ?? roster.find(r => !r.isBenchmark) ?? roster[0] ?? null;
}

/** 1 -> '1 share', 3 -> '3 shares', 2.50004 -> '2.5 shares'. Book shares are fractional to 4 dp. */
export function sharesLabel(n: number): string {
  const v = Number(n.toFixed(4));
  return v === 1 ? '1 share' : `${v} shares`;
}

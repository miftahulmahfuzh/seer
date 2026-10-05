import { BookOpen, BrainCircuit, Gauge, Gavel, Landmark, Shield, Sigma, type LucideIcon } from 'lucide-react';

// The `icon` column of `strategies` names a Lucide icon (kebab-case). Roster: landmark (SPY),
// sigma (A), trending-up (F4), shield (F1), gavel (C, migration 004), book-open (FND); brain-circuit kept for old demo rows.
// F4's stored 'trending-up' draws Gauge: History's "Wins only" filter already uses TrendingUp.
const ICONS: Record<string, LucideIcon> = {
  landmark: Landmark,
  sigma: Sigma,
  'trending-up': Gauge,
  shield: Shield,
  'brain-circuit': BrainCircuit,
  gavel: Gavel,
  'book-open': BookOpen,
};

/** The Lucide icon a strategies row names; Sigma when the name is unknown. */
export const strategyIcon = (name: string): LucideIcon => ICONS[name] ?? Sigma;

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

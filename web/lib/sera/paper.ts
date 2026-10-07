/**
 * Which lab method each paper roster entry came from, read out of the lab snapshot's `paper`
 * block (`paper.roster.LAB_PROVENANCE`, snapshot v3).
 *
 * Its own module rather than an export of `./lab`, because its one caller is the leaderboard,
 * which is not a Sera page: `lab.ts` throws at import time on a snapshot whose gate block it
 * cannot read, and a stale `lab.json` must not be able to take the leaderboard down with /sera.
 * Server components only — the import pulls in the whole snapshot, which must never ship to the
 * browser.
 */
import raw from '../../data/lab.json';
import type { LabPaper } from './types';

const byStrategy = new Map(
  ((raw as unknown as { paper?: LabPaper[] }).paper ?? []).map((p) => [p.strategyId, p]),
);

/**
 * A roster entry's lab provenance, or null when it has none. C and SPY are not lab methods and
 * never will be: null is the ordinary answer here, not a missing-data signal.
 */
export const paperOf = (strategyId: string): LabPaper | null => byStrategy.get(strategyId) ?? null;

/** The href of a strategy's method page, or null when it did not come from the lab. */
export function methodHref(strategyId: string): string | null {
  const p = paperOf(strategyId);
  return p ? `/sera/methods/${encodeURIComponent(p.methodId)}` : null;
}

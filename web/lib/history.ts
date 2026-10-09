// What the History page says when it has nothing to show, and what one fill was.
//
// The empty state is here rather than inline because it was wrong in a way that cost the owner a
// bug report (2026-10-09): the list said "No trades match these filters" for a strategy that had
// bought twenty names two days earlier and sold none of them. The filters were not the reason --
// MOM holds its basket for a month, so its first closed trade cannot exist before November -- and
// a sentence that points at the wrong cause is worse than no sentence. No database access, so the
// page and the tests share one answer.
import { cadenceOf, sellsWhen } from './cadence';

/** Which list is empty: the closed-trade ledger, or the buy-and-sell log. */
export type EmptyWhat = 'trades' | 'activity';

/** The fields of a roster row this module reads. */
export type EmptyStrategy = { name: string; rulesId: string | null; paperStart: string | null };

export type EmptyNote = { title: string; sub: string };

export type EmptyArgs = {
  what: EmptyWhat;
  /** The selected strategy, or null when every strategy is shown. */
  strategy: EmptyStrategy | null;
  outcome: 'all' | 'win' | 'loss';
};

const STILL_OPEN = 'Every position bought so far is still open; a trade lands here when one closes.';

/**
 * Why this list is empty, in a title and one sentence.
 *
 * The order matters and is the whole point. A narrowing filter is named first, because then the
 * filter really IS the reason. Otherwise the reason is the strategy's own cadence, which is a
 * fact about when it can sell at all -- never a date, because the NYSE calendar is the engine's
 * and `lib/session.ts` does not model holidays.
 */
export function emptyNote({ what, strategy, outcome }: EmptyArgs): EmptyNote {
  if (what === 'activity') {
    return strategy && strategy.paperStart === null
      ? { title: 'Not started', sub: `${strategy.name} has not started trading, so it has bought nothing.` }
      : { title: 'Nothing bought yet', sub: 'Every buy and sell the engine makes is listed here, newest first.' };
  }

  if (outcome !== 'all') {
    const word = outcome === 'win' ? 'wins' : 'losses';
    return {
      title: outcome === 'win' ? 'No winners yet' : 'No losers yet',
      sub: `No closed trade here is one of the ${word}. Clear the filter to see every closed trade.`,
    };
  }

  if (strategy === null) return { title: 'Nothing sold yet', sub: STILL_OPEN };

  if (strategy.paperStart === null) {
    return { title: 'Not started', sub: `${strategy.name} has not started trading yet, so it has sold nothing.` };
  }

  // A cadence this build has not been taught still gets a true sentence, just a vaguer one.
  const when = sellsWhen(cadenceOf(strategy.rulesId));
  const why = when === null
    ? `${strategy.name} has sold nothing; every position it has bought is still open.`
    : `${strategy.name} has sold nothing: ${when}.`;
  return { title: 'Nothing sold yet', sub: `${why} Its buys are under Activity.` };
}

/**
 * What one fill was, from its side and the engine's own reason.
 *
 * Keys are `sim.book.FillReason` and migration 003's `book_fills_reason_check`; the two sell
 * reasons a bracket order can carry (`tp`, `sl`, `time`, `gap`) are in the same table because the
 * Activity list shows both engines' fills in one column.
 */
export const FILL_REASON: Record<string, string> = {
  entry: 'Bought',
  add: 'Topped up',
  trim: 'Trimmed',
  signal: 'Sold',
  time: 'Time exit',
  gap: 'Gapped out',
  tp: 'Target hit',
  sl: 'Stopped out',
  forced: 'Force closed',
};

export function fillVerb(side: 'buy' | 'sell', reason: string): string {
  return FILL_REASON[reason] ?? (side === 'buy' ? 'Bought' : 'Sold');
}

/** The History page's query: strategy, the active view's filter, and the view. */
export type HistoryQuery = { s?: string; o?: string; v?: string };

/**
 * `/history?...` with `next` applied over `now`.
 *
 * One `o` param serves both views, because they are never on screen together -- Trades filters
 * `win`/`loss`, Activity filters `buy`/`sell`. Switching view therefore DROPS it: carrying
 * `o=buy` into Trades would put `aria-current` on nothing and leave the user looking at an
 * unfiltered list with no button lit. Defaults (`all`, `trades`) are omitted so the plain
 * `/history` stays the canonical URL.
 */
export function historyHref(now: Required<HistoryQuery>, next: HistoryQuery): string {
  const p = new URLSearchParams();
  const s = next.s ?? now.s;
  const v = next.v ?? now.v;
  const o = next.o ?? (v === now.v ? now.o : 'all');
  if (s !== 'all') p.set('s', s);
  if (o !== 'all') p.set('o', o);
  if (v !== 'trades') p.set('v', v);
  const qs = p.toString();
  return qs ? `/history?${qs}` : '/history';
}

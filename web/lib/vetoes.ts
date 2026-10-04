// Pure helpers for the news check's verdicts (`news_vetoes`, migration 004; strategy C, handover
// D6/D10). No database access: lib/data reads the rows, Positions renders what these return.

/** The stored verdict. Anything else reads as 'failed': a failed check is no trade (design §8). */
export type Verdict = 'allow' | 'veto' | 'failed';

/** One candidate's verdict for one session, as Positions shows it. */
export type Veto = {
  /** Rank in A's ranked list for the session (1..10). */
  rank: number;
  symbol: string;
  verdict: Verdict;
  /** The LLM's one sentence, or why the check failed (redacted by the engine). */
  reason: string;
  /** Headlines the check saw (jsonb_array_length(headlines)). */
  headlineCount: number;
  /** Scheduled earnings found inside the holding window, if any. */
  earningsDate: string | null;
  /** The veto run's start: the news cutoff (ISO, UTC). */
  decidedAt: string;
};

/** Never assumes 'allow': an unknown value is a failed check. */
export function parseVerdict(v: unknown): Verdict {
  return v === 'allow' || v === 'veto' ? v : 'failed';
}

/**
 * What the "Vetoed tonight" sheet shows:
 * - 'missing': no verdict rows for the session, so the strategy buys nothing that session. `veto`
 *   writes no rows when A had no candidates, so this cannot be told apart from a check that did not
 *   run (or came after Paper had decided); `noCheckLine` says so;
 * - 'failed': every check failed for the same reason (no keys, wrong model, ...), shown once;
 * - 'listed': the vetoed and failed candidates (possibly none), by rank.
 */
export type VetoSheet =
  | { state: 'missing' }
  | { state: 'failed'; checked: number; reason: string }
  | { state: 'listed'; checked: number; allowed: number; rows: Veto[] };

export function vetoSheet(rows: Veto[]): VetoSheet {
  if (rows.length === 0) return { state: 'missing' };
  const sorted = [...rows].sort((a, b) => a.rank - b.rank);
  const reasons = new Set(sorted.map(r => r.reason));
  if (sorted.every(r => r.verdict === 'failed') && reasons.size === 1) {
    return { state: 'failed', checked: sorted.length, reason: sorted[0].reason };
  }
  return {
    state: 'listed',
    checked: sorted.length,
    allowed: sorted.filter(r => r.verdict === 'allow').length,
    rows: sorted.filter(r => r.verdict !== 'allow'),
  };
}

/** '8 checked · 5 allowed' */
export const checkedLine = (checked: number, allowed: number) => `${checked} checked · ${allowed} allowed`;

/** 0 -> 'No headlines', 1 -> '1 headline', 12 -> '12 headlines' */
export const headlinesLabel = (k: number) => (k === 0 ? 'No headlines' : k === 1 ? '1 headline' : `${k} headlines`);

/**
 * The 'missing' sheet's line (`day` already formatted, `short` the strategy's short label). Honest about
 * what the app cannot know: no rows means A had no candidates or the check did not run.
 */
export const noCheckLine = (day: string, short: string) =>
  `No news check for ${day}: A had no candidates, or the check did not run. ${short} buys nothing this session.`;

/**
 * The owner's list of stocks Gotrade does not offer (table unavailable_symbols,
 * db/migrations/014_unavailable.sql). Seer's paper methods skip every stock on it and pick the
 * next-best one instead.
 *
 * Server only -- it opens the Neon connection from lib/db. The pure rules live in
 * ./gotrade-symbol, which client code and tests import instead.
 *
 * Rows are never deleted: the engine replays history against them. Removing a stock closes its
 * open row (until = the day after the latest paper session) instead.
 */
import { sql } from '@/lib/db';

export { MAX_NOTE, normalizeNote, normalizeSymbol } from './gotrade-symbol';

/** A stock on the list right now. Dates are Jakarta calendar days, YYYY-MM-DD. */
export type ListedStock = { symbol: string; note: string | null; added: string };
/** A stock that was on the list and is back on Gotrade. */
export type BackOnGotrade = ListedStock & { removed: string };

export type GotradeList = { listed: ListedStock[]; back: BackOnGotrade[] };

/** How many "back on Gotrade" rows the page shows: the most recent few, not the whole history. */
export const BACK_SHOWN = 6;

/**
 * The open list, by ticker, plus the few most recently removed. Returns null when Neon cannot be
 * read, so the page can say so rather than show an empty list it cannot stand behind.
 */
export async function gotradeList(): Promise<GotradeList | null> {
  try {
    const [listed, back] = await Promise.all([
      sql`
        SELECT symbol, note, to_char(added_at AT TIME ZONE 'Asia/Jakarta', 'YYYY-MM-DD') AS added
          FROM unavailable_symbols
         WHERE until IS NULL
         ORDER BY symbol`,
      sql`
        SELECT symbol, note,
               to_char(added_at AT TIME ZONE 'Asia/Jakarta', 'YYYY-MM-DD') AS added,
               to_char(COALESCE(removed_at, added_at) AT TIME ZONE 'Asia/Jakarta', 'YYYY-MM-DD') AS removed
          FROM unavailable_symbols u
         WHERE until IS NOT NULL
           AND NOT EXISTS (SELECT 1 FROM unavailable_symbols o WHERE o.symbol = u.symbol AND o.until IS NULL)
         ORDER BY removed_at DESC NULLS LAST, id DESC
         LIMIT ${BACK_SHOWN * 4}`,
    ]);
    // One line per stock in the history, however many times it came and went.
    const seen = new Set<string>();
    const backRows: BackOnGotrade[] = [];
    for (const r of back) {
      if (seen.has(r.symbol)) continue;
      seen.add(r.symbol);
      backRows.push({ symbol: r.symbol, note: r.note ?? null, added: r.added, removed: r.removed });
      if (backRows.length === BACK_SHOWN) break;
    }
    return {
      listed: listed.map(r => ({ symbol: r.symbol, note: r.note ?? null, added: r.added })),
      back: backRows,
    };
  } catch (e) {
    console.error('unavailable_symbols read failed', e);
    return null;
  }
}

/**
 * Puts `symbol` on the list from the latest paper session on. `symbol` and `note` must already be
 * normalized. Returns 'already' when it is listed (the open index makes this idempotent).
 * Throws when the write fails.
 */
export async function addUnavailable(symbol: string, note: string | null): Promise<'added' | 'already'> {
  const rows = await sql`
    INSERT INTO unavailable_symbols (symbol, since, note)
    VALUES (${symbol}, (SELECT COALESCE(MAX(last_session), CURRENT_DATE) FROM paper_state), ${note})
    ON CONFLICT (symbol) WHERE until IS NULL DO NOTHING
    RETURNING id`;
  return rows.length > 0 ? 'added' : 'already';
}

/**
 * Takes `symbol` off the list: closes its open row from the session after the latest paper one.
 * Returns false when it was not listed. Throws when the write fails.
 */
export async function removeUnavailable(symbol: string): Promise<boolean> {
  const rows = await sql`
    UPDATE unavailable_symbols
       SET until = GREATEST(since, (SELECT COALESCE(MAX(last_session), CURRENT_DATE) FROM paper_state) + 1),
           removed_at = now()
     WHERE symbol = ${symbol} AND until IS NULL
    RETURNING id`;
  return rows.length > 0;
}

/** Whether a change can ask the engine to re-pick at once, or has to wait for the nightly run. */
export const repickConfigured = (): boolean => Boolean(process.env.GITHUB_DISPATCH_TOKEN);

/**
 * Asks GitHub to run the engine's re-pick workflow now. Never throws: a failed or unconfigured
 * dispatch only means the change is picked up at the next nightly run. Returns whether it was sent.
 */
export async function dispatchRepick(): Promise<boolean> {
  const token = process.env.GITHUB_DISPATCH_TOKEN;
  if (!token) {
    console.log('repick dispatch skipped: GITHUB_DISPATCH_TOKEN is not set');
    return false;
  }
  try {
    const res = await fetch(
      'https://api.github.com/repos/miftahulmahfuzh/seer/actions/workflows/repick.yml/dispatches',
      {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          Accept: 'application/vnd.github+json',
          'Content-Type': 'application/json',
          'X-GitHub-Api-Version': '2022-11-28',
        },
        body: JSON.stringify({ ref: 'main' }),
        signal: AbortSignal.timeout(8000),
      },
    );
    if (!res.ok) {
      console.error('repick dispatch failed', res.status, await res.text().catch(() => ''));
      return false;
    }
    return true;
  } catch (e) {
    console.error('repick dispatch failed', e);
    return false;
  }
}

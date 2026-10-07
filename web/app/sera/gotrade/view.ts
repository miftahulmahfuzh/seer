// Pure helpers for /sera/gotrade: the plain sentences the page and its forms show. No data access.

/** What a form shows after the owner adds or removes a stock. */
export type FormState = { tone: 'idle' | 'ok' | 'error'; message: string };

export const IDLE: FormState = { tone: 'idle', message: '' };

/** When the picks catch up with the list: right away when the re-pick was asked for, else overnight. */
export const whenRepicked = (live: boolean): string =>
  live ? 'within a few minutes' : 'at the next nightly run';

/** The standing line under the list: what happens to a pick that holds a listed stock. */
export function repickLine(live: boolean): string {
  return `Any pick holding a stock on this list is re-chosen ${whenRepicked(live)}, using the next-best stock instead.`;
}

export const BAD_SYMBOL: FormState = {
  tone: 'error',
  message: 'That does not look like a ticker. Type it as Gotrade or Yahoo shows it, like AAPL or BRK.B.',
};

export const NOT_ALLOWED: FormState = { tone: 'error', message: 'Only the owner can change this list.' };

export const WRITE_FAILED: FormState = {
  tone: 'error',
  message: 'The list could not be saved just now. Nothing changed; try again in a moment.',
};

export function addedState(symbol: string, result: 'added' | 'already', live: boolean): FormState {
  return result === 'already'
    ? { tone: 'ok', message: `${symbol} is already on the list.` }
    : { tone: 'ok', message: `${symbol} is on the list. Seer will skip it, and picks are re-chosen ${whenRepicked(live)}.` };
}

export function removedState(symbol: string, removed: boolean, live: boolean): FormState {
  return removed
    ? { tone: 'ok', message: `${symbol} is back on Gotrade. Seer may pick it again ${whenRepicked(live)}.` }
    : { tone: 'ok', message: `${symbol} was not on the list.` };
}

/** '3 stocks' / '1 stock' / 'No stocks'. */
export const stockCount = (n: number): string => (n === 0 ? 'No stocks' : n === 1 ? '1 stock' : `${n} stocks`);

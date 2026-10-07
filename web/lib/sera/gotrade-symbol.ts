// Pure rules for the "Not on Gotrade" list. No data access, so tests and client islands may
// import it; lib/sera/gotrade.ts (server only) re-exports these and does the reading/writing.

/** A canonical ticker: uppercase letters and digits, an optional one-letter share class (BRK.B). */
const SYMBOL = /^[A-Z][A-Z0-9]*(\.[A-Z])?$/;

/** The longest note kept with a listed stock. Anything past it is cut. */
export const MAX_NOTE = 200;

/**
 * The ticker as the engine stores it -- trimmed, uppercase, with '-' or '/' before a share
 * class turned into '.' (brk-b, BRK/B and BRK.B are all BRK.B) -- or null when it is not a ticker.
 */
export function normalizeSymbol(raw: unknown): string | null {
  if (typeof raw !== 'string') return null;
  const s = raw.trim().toUpperCase().replace(/[-/]/g, '.');
  return SYMBOL.test(s) ? s : null;
}

/** An optional note: trimmed, inner whitespace collapsed, capped at MAX_NOTE; empty means none. */
export function normalizeNote(raw: unknown): string | null {
  if (typeof raw !== 'string') return null;
  const s = raw.replace(/\s+/g, ' ').trim();
  return s ? s.slice(0, MAX_NOTE) : null;
}

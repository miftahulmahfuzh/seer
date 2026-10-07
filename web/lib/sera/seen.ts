/**
 * Reader state for /sera/journal: which lab insights have already been seen.
 *
 * Server only -- it opens the Neon connection from lib/db. Never import it from a client
 * component, and never from app/sera/journal/view.ts: that module stays pure and takes the seen
 * set as a plain `ReadonlySet<number>` parameter (plan invariant 3).
 *
 * Lab FACTS still come only from the committed snapshot (lib/sera/lab.ts). Which entries the
 * reader has seen is the one Sera thing that lives in Postgres, because it is state about the
 * reader, not about the lab.
 */
import { sql } from '@/lib/db';

/** How an entry came to be marked seen. Mirrors journal_seen.via's CHECK (012_journal_seen.sql). */
export type SeenVia = 'view' | 'click';

/**
 * The most ids one POST may carry. The whole Journal is 26 entries today and a reader cannot
 * dwell on more than a screenful at a time, so this is a guard against a malformed or hostile
 * body, not a working limit.
 *
 * PAIRED WITH MAX_BATCH in app/sera/journal/seen-client.ts (50), which is the client's own,
 * smaller cap on one flush. The invariant between them is MAX_BATCH <= MAX_SEEN_BATCH; 50 <= 500
 * holds with room to spare. They cannot share a constant -- this module is server-only and builds
 * the Neon client at module scope, so the island cannot import it -- so if either number changes,
 * check the other. A client cap above this one turns every full flush into a silent 400: the
 * route returns no body and the island swallows failures, so nothing would surface it.
 */
export const MAX_SEEN_BATCH = 500;

/** Every seen id. Throws when Postgres is unreachable; the exported readers below catch. */
async function fetchSeenIds(): Promise<Set<number>> {
  // insight_id is bigint, which the driver returns as a string: Number() it, like lib/data.ts.
  const rows = await sql`SELECT insight_id FROM journal_seen`;
  return new Set<number>(rows.map(r => Number(r.insight_id)));
}

/**
 * Every insight id marked seen, as a set the view layer can probe.
 *
 * Never throws (plan invariant 9). An empty table and an unreachable database both read as
 * "nothing seen yet", so the Journal renders with every entry unseen rather than 500ing because
 * Neon is down.
 */
export async function seenInsightIds(): Promise<Set<number>> {
  try {
    return await fetchSeenIds();
  } catch (e) {
    console.error('journal_seen read failed; treating every entry as unseen', e);
    return new Set<number>();
  }
}

/**
 * How many of `insightIds` are NOT yet seen, or `null` when the read failed.
 *
 * The caller passes the ids rather than this module reaching for the snapshot, so that importing
 * it from the API route does not drag web/data/lab.json (0.89 MB) into that route's bundle.
 * `null` lets the Sera rail show no badge at all rather than a number it cannot stand behind.
 */
export async function unseenCount(insightIds: Iterable<number>): Promise<number | null> {
  let seen: Set<number>;
  try {
    seen = await fetchSeenIds();
  } catch (e) {
    console.error('journal_seen read failed; no unseen count', e);
    return null;
  }
  let n = 0;
  for (const id of insightIds) if (!seen.has(id)) n += 1;
  return n;
}

/**
 * The `ids` of a POST body, cleaned: positive safe integers only, deduplicated, order preserved.
 * Returns null when the input is not an array, is empty, holds anything that is not an id, or is
 * longer than MAX_SEEN_BATCH -- all of which the route answers with 400.
 *
 * Safe integers only because insight_id is a bigint column read back through JS numbers; an id
 * past 2^53-1 could not survive the round trip, and the lab is at id 26.
 */
export function normalizeSeenIds(raw: unknown): number[] | null {
  if (!Array.isArray(raw) || raw.length === 0 || raw.length > MAX_SEEN_BATCH) return null;
  const out: number[] = [];
  const got = new Set<number>();
  for (const v of raw) {
    if (typeof v !== 'number' || !Number.isSafeInteger(v) || v <= 0) return null;
    if (got.has(v)) continue;
    got.add(v);
    out.push(v);
  }
  return out.length === 0 ? null : out;
}

/**
 * The `via` of a POST body. Absent (or null) means 'view', the ordinary case; anything that is
 * not one of the two the CHECK constraint allows returns null, which the route answers with 400.
 */
export function parseSeenVia(raw: unknown): SeenVia | null {
  if (raw === undefined || raw === null) return 'view';
  return raw === 'view' || raw === 'click' ? raw : null;
}

/**
 * Marks `ids` seen, idempotently: a row that already exists is left exactly as it was, so the
 * first marking's seen_at and via win and nothing is ever un-seen (plan invariant 6). Returns how
 * many rows were new.
 *
 * `ids` must already have been through normalizeSeenIds. Throws when the write fails -- the route
 * turns that into a 500 and the client island simply keeps the ids queued for its next flush.
 *
 * The ids travel as one JSON string parameter rather than a Postgres array: nothing else in this
 * app passes an array to the Neon driver, and a string with an explicit ::jsonb cast needs no
 * assumption about how the HTTP protocol serialises one.
 */
export async function markInsightsSeen(ids: number[], via: SeenVia): Promise<number> {
  if (ids.length === 0) return 0;
  const rows = await sql`
    INSERT INTO journal_seen (insight_id, via)
    SELECT value::bigint, ${via}
      FROM jsonb_array_elements_text(${JSON.stringify(ids)}::jsonb) AS t(value)
    ON CONFLICT (insight_id) DO NOTHING
    RETURNING insight_id
  `;
  return rows.length;
}

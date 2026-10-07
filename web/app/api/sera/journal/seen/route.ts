import { auth } from '@/auth';
import { isAllowed } from '@/lib/allow';
import { isSeraUser } from '@/lib/sera/access';
import { markInsightsSeen, normalizeSeenIds, parseSeenVia } from '@/lib/sera/seen';

// Reads cookies and writes a row: never cached, never prerendered. Matches the convention the
// app/(app) pages follow once they touch Neon.
export const dynamic = 'force-dynamic';

/** Every answer this route gives is a status code and nothing else. */
const empty = (status: number) => new Response(null, { status });

/**
 * The /sera gate, in status-code form. Exactly the rule lib/sera/gate.ts's requireSera applies --
 * signed in, inside ALLOWED_EMAIL, and SERA_EMAIL -- read from the same two predicates so the two
 * cannot drift. requireSera itself is unusable here: its redirect()/notFound() are navigation
 * responses, and a 307 to /signin would tell a stranger the section exists (plan invariant 7).
 */
async function isSeraCaller(): Promise<boolean> {
  const session = await auth();
  const email = session?.user?.email;
  return isAllowed(email, process.env.ALLOWED_EMAIL) && isSeraUser(email);
}

/**
 * POST /api/sera/journal/seen -- mark Journal entries seen.
 *
 * Body: {"ids": number[], "via"?: "view" | "click"}, at most 500 ids, each a positive integer.
 * "via" defaults to "view". Answers 204 on success, 400 on a malformed body, 404 to anyone the
 * /sera gate rejects, 500 when the write fails. The response never carries a body: the client
 * flushes this with navigator.sendBeacon, which cannot read one.
 *
 * The body is read as text and parsed by hand rather than with req.json(): sendBeacon sends a
 * Blob, so the Content-Type on the wire is whatever that Blob was built with (text/plain is the
 * type every browser permits without a preflight). Content-Type is therefore ignored entirely,
 * and one try/catch covers every way the payload can fail to be JSON.
 */
export async function POST(req: Request) {
  if (!(await isSeraCaller())) return empty(404);

  let body: unknown;
  try {
    body = JSON.parse(await req.text());
  } catch {
    return empty(400);
  }
  if (typeof body !== 'object' || body === null || Array.isArray(body)) return empty(400);

  const ids = normalizeSeenIds((body as { ids?: unknown }).ids);
  const via = parseSeenVia((body as { via?: unknown }).via);
  if (!ids || !via) return empty(400);

  try {
    await markInsightsSeen(ids, via);
  } catch (e) {
    // Marking seen is soft state. Log it and let the client requeue; never make the reader care.
    console.error('journal_seen write failed', e);
    return empty(500);
  }
  return empty(204);
}

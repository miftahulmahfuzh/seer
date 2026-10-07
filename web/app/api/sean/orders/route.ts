import { createHash } from 'node:crypto';
import { orderById, orderIdBySha, saveOrder } from '@/lib/sean/data';
import { isSeanCaller } from '@/lib/sean/gate';
import { archiveReceipt, receiptDepsFromEnv, type ArchiveOutcome } from '@/lib/sean/receipts';
import { isReaderDown, readOrder, visionDeps, type ReadOrderOutcome } from '@/lib/sean/readOrder';
import { visionConfigFromEnv } from '@/lib/sean/vision';
import { parseUploadBody } from '@/app/sean/trades/upload';
import { SAY } from '@/app/sean/trades/view';

// Reads cookies, calls the vision model, writes a row: never cached, never prerendered.
export const dynamic = 'force-dynamic';
// GLM-4.6V takes 5-40 s per picture. Must stay a literal number (read at build time).
export const maxDuration = 60;

const fail = (status: number, error: string) => Response.json({ error }, { status });

/**
 * POST /api/sean/orders -- read one Gotrade Order Summary screenshot and keep the order.
 *
 * Body: {"image": base64 JPEG without a data: prefix, "sha256": hex of the decoded bytes}.
 * 201 {order} new; 200 {order, duplicate: true} same picture or same order already kept;
 * 400 malformed or damaged; 413 over 1.5 MB; 422 not a readable, filled receipt (Phase 1's
 * plain-words message); 502 the reader is missing, unreachable, timed out or did not see the
 * picture, or its copy could not be kept; 500 the save failed; 404 to anyone but the owner.
 * Every new picture is committed to the repo's sean-receipts branch (lib/sean/receipts.ts) while
 * it is read -- refused ones too, so the trail holds everything the owner sent -- and an order is
 * saved only once its screenshot is kept.
 */
export async function POST(req: Request) {
  if (!(await isSeanCaller())) return new Response(null, { status: 404 });

  let body: unknown;
  try {
    body = JSON.parse(await req.text());
  } catch {
    return fail(400, SAY.damaged);
  }
  const upload = parseUploadBody(body);
  if (!upload.ok) return fail(upload.status, upload.status === 413 ? SAY.tooLarge : SAY.damaged);

  // The client's digest must be of the bytes that arrived: it is the dedupe key.
  const sha = createHash('sha256').update(Buffer.from(upload.image, 'base64')).digest('hex');
  if (sha !== upload.sha256) return fail(400, SAY.damaged);

  try {
    const known = await orderIdBySha(sha);
    if (known !== null) {
      const order = await orderById(known);
      if (order) return Response.json({ order, duplicate: true }, { status: 200 });
    }
  } catch (e) {
    console.error('sean_orders read failed', e);
    return fail(500, SAY.saveFailed);
  }

  // Runs beside the read and never rejects; every return below waits for it, so the commit is
  // not cut off when the response ends the function.
  const receiptDeps = receiptDepsFromEnv();
  const keeping: Promise<ArchiveOutcome> = receiptDeps
    ? archiveReceipt(receiptDeps, sha, upload.image)
    : Promise.resolve({ ok: false, detail: 'GITHUB_DISPATCH_TOKEN is not set' });
  const kept = async () => {
    const k = await keeping;
    if (!k.ok) console.error('sean: screenshot not kept', sha, k.detail);
    return k.ok;
  };

  const config = visionConfigFromEnv();
  if (!config) {
    console.error('sean: LLM_API_KEY, LLM_VISION_BASE_URL or LLM_VISION_MODEL is not set (or is the /api/anthropic URL)');
    await kept();
    return fail(502, SAY.notSetUp);
  }

  // Phase 1's readOrder never throws for a model problem: vision, JSON, the arithmetic checks
  // (toOrder also refuses every status but "Filled") and at most one image-carrying repair, all
  // inside its 55 s budget (READ_BUDGET_MS). It rethrows only an error that is not the reader's.
  let out: ReadOrderOutcome;
  try {
    out = await readOrder(visionDeps(config), upload.image);
  } catch (e) {
    console.error('sean: read failed unexpectedly', e);
    await kept();
    return fail(502, SAY.readerDown);
  }
  if (!out.ok) {
    // detail and issues are for the logs only; out.message is already plain words for the owner.
    console.warn('sean: receipt refused', out.code, out.detail ?? out.issues.join(' | '));
    await kept();
    return fail(isReaderDown(out.code) ? 502 : 422, out.message);
  }

  if (!(await kept())) return fail(502, SAY.notKept);

  try {
    const saved = await saveOrder(out.order, sha, out.raw);
    const order = await orderById(saved.id);
    if (!order) throw new Error('the saved order could not be read back');
    return saved.duplicate
      ? Response.json({ order, duplicate: true }, { status: 200 })
      : Response.json({ order }, { status: 201 });
  } catch (e) {
    console.error('sean_orders write failed', e);
    return fail(500, SAY.saveFailed);
  }
}

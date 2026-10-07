import { orderSha } from '@/lib/sean/data';
import { isSeanCaller } from '@/lib/sean/gate';
import { fetchReceipt, receiptDepsFromEnv } from '@/lib/sean/receipts';
import { parseOrderId } from '@/app/sean/trades/view';

// Reads cookies and Neon: never cached by Next, never prerendered.
export const dynamic = 'force-dynamic';

/**
 * GET /api/sean/orders/:id/image -- the original Order Summary screenshot an order was read
 * from, out of the repo's sean-receipts branch (lib/sean/receipts.ts).
 * 200 image/jpeg; 404 no such order, no copy kept, or anyone but the owner; 502 GitHub failed.
 */
export async function GET(_req: Request, { params }: { params: Promise<{ id: string }> }) {
  if (!(await isSeanCaller())) return new Response(null, { status: 404 });
  const id = parseOrderId((await params).id);
  if (id === null) return new Response(null, { status: 404 });

  const deps = receiptDepsFromEnv();
  if (!deps) {
    console.error('sean: GITHUB_DISPATCH_TOKEN is not set; screenshots cannot be shown');
    return new Response(null, { status: 502 });
  }
  try {
    const sha = await orderSha(id);
    const bytes = sha === null ? null : await fetchReceipt(deps, sha);
    if (bytes === null) return new Response(null, { status: 404 });
    return new Response(bytes, {
      headers: {
        'Content-Type': 'image/jpeg',
        // Named by content and never changed: the browser may keep it, nobody else may.
        'Cache-Control': 'private, max-age=31536000, immutable',
      },
    });
  } catch (e) {
    console.error('sean: screenshot read failed', id, e);
    return new Response(null, { status: 502 });
  }
}

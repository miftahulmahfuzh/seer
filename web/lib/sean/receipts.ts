/**
 * The audit trail: every uploaded Order Summary screenshot, kept byte for byte in the repo on
 * the `sean-receipts` branch as `receipts/<sha256>.jpg` (the same digest as
 * sean_orders.image_sha256). Written once per picture through GitHub's contents API, never
 * edited or deleted -- deleting an order keeps its screenshot. Vercel skips building the branch
 * (the project's ignored-build-step command).
 *
 * Pure apart from the injected `fetch`, so it is unit-tested without a network.
 */

export const RECEIPTS_REPO = 'miftahulmahfuzh/seer';
export const RECEIPTS_BRANCH = 'sean-receipts';

const SHA256 = /^[0-9a-f]{64}$/;
/** Three uploads at a time race for the branch head; GitHub answers the losers 409. */
const CONFLICT_RETRIES = 5;

export type ReceiptDeps = {
  token: string;
  fetch: typeof fetch;
  /** Waits between conflict retries; injectable so tests do not sleep. */
  sleep?: (ms: number) => Promise<void>;
};

export type ArchiveOutcome = { ok: true; already: boolean } | { ok: false; detail: string };

export const receiptPath = (sha: string): string => `receipts/${sha}.jpg`;

const contentsUrl = (sha: string) => `https://api.github.com/repos/${RECEIPTS_REPO}/contents/${receiptPath(sha)}`;

const headers = (token: string, accept = 'application/vnd.github+json') => ({
  Authorization: `Bearer ${token}`,
  Accept: accept,
  'X-GitHub-Api-Version': '2022-11-28',
});

/** The token the receipts and the Sean dispatch share (contents + actions on this repo). */
export function receiptDepsFromEnv(env: Record<string, string | undefined> = process.env): ReceiptDeps | null {
  const token = env.GITHUB_DISPATCH_TOKEN;
  return token ? { token, fetch: globalThis.fetch.bind(globalThis) } : null;
}

/**
 * Commits one screenshot. A picture that is already there (GitHub's 422 `"sha" wasn't supplied`
 * for a path that exists) counts as kept. Never throws.
 */
export async function archiveReceipt(deps: ReceiptDeps, sha: string, imageB64: string): Promise<ArchiveOutcome> {
  if (!SHA256.test(sha)) return { ok: false, detail: 'not a sha256' };
  const sleep = deps.sleep ?? ((ms: number) => new Promise<void>(r => setTimeout(r, ms)));
  const body = JSON.stringify({
    message: `receipt ${sha.slice(0, 12)}`,
    content: imageB64,
    branch: RECEIPTS_BRANCH,
  });
  let detail = '';
  for (let attempt = 0; attempt <= CONFLICT_RETRIES; attempt++) {
    try {
      const res = await deps.fetch(contentsUrl(sha), {
        method: 'PUT',
        headers: { ...headers(deps.token), 'Content-Type': 'application/json' },
        body,
        signal: AbortSignal.timeout(15_000),
      });
      if (res.status === 200 || res.status === 201) return { ok: true, already: false };
      const text = await res.text().catch(() => '');
      if (res.status === 422 && text.includes("wasn't supplied")) return { ok: true, already: true };
      detail = `${res.status} ${text.slice(0, 200)}`;
      if (res.status !== 409) return { ok: false, detail };
    } catch (e) {
      detail = e instanceof Error ? e.message : String(e);
    }
    if (attempt < CONFLICT_RETRIES) await sleep(250 * (attempt + 1) + Math.floor(Math.random() * 250));
  }
  return { ok: false, detail };
}

/** The kept screenshot's bytes; null when none was kept for this digest. Throws on other failures. */
export async function fetchReceipt(deps: ReceiptDeps, sha: string): Promise<Uint8Array<ArrayBuffer> | null> {
  if (!SHA256.test(sha)) return null;
  const res = await deps.fetch(`${contentsUrl(sha)}?ref=${RECEIPTS_BRANCH}`, {
    headers: headers(deps.token, 'application/vnd.github.raw'),
    signal: AbortSignal.timeout(15_000),
  });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`receipt fetch ${res.status}`);
  return new Uint8Array(await res.arrayBuffer());
}

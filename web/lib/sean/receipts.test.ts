import { describe, expect, it, vi } from 'vitest';
import { RECEIPTS_BRANCH, archiveReceipt, fetchReceipt, receiptDepsFromEnv, receiptPath } from './receipts';

// No network anywhere in this file: every case injects `fetch`.

const SHA = 'a'.repeat(64);
const IMG = '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAA==';
const noSleep = async () => {};

const reply = (status: number, body = '{}') => new Response(body, { status });

function deps(...replies: Array<Response | Error>) {
  const fetch = vi.fn(async () => {
    const next = replies.shift();
    if (next === undefined) throw new Error('unexpected call');
    if (next instanceof Error) throw next;
    return next;
  });
  return { token: 't0k', fetch: fetch as unknown as typeof globalThis.fetch, sleep: noSleep, calls: fetch };
}

describe('receiptPath', () => {
  it('names the file by its digest', () => {
    expect(receiptPath(SHA)).toBe(`receipts/${SHA}.jpg`);
  });
});

describe('receiptDepsFromEnv', () => {
  it('needs the GitHub token', () => {
    expect(receiptDepsFromEnv({})).toBeNull();
    expect(receiptDepsFromEnv({ GITHUB_DISPATCH_TOKEN: 'x' })?.token).toBe('x');
  });
});

describe('archiveReceipt', () => {
  it('commits the picture to the receipts branch', async () => {
    const d = deps(reply(201));
    expect(await archiveReceipt(d, SHA, IMG)).toEqual({ ok: true, already: false });
    const [url, init] = d.calls.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(`https://api.github.com/repos/miftahulmahfuzh/seer/contents/receipts/${SHA}.jpg`);
    expect(init.method).toBe('PUT');
    expect((init.headers as Record<string, string>).Authorization).toBe('Bearer t0k');
    const body = JSON.parse(init.body as string);
    expect(body).toMatchObject({ content: IMG, branch: RECEIPTS_BRANCH });
  });

  it('counts a picture that is already kept as kept (GitHub 422, escaped as it really is)', async () => {
    const d = deps(reply(422, '{"message":"Invalid request.\\n\\n\\"sha\\" wasn\'t supplied.","status":"422"}'));
    expect(await archiveReceipt(d, SHA, IMG)).toEqual({ ok: true, already: true });
  });

  it('fails on any other 422', async () => {
    const d = deps(reply(422, '{"message":"content is not valid Base64"}'));
    expect(await archiveReceipt(d, SHA, IMG)).toMatchObject({ ok: false });
  });

  it('retries when a parallel upload moved the branch head (409)', async () => {
    const d = deps(reply(409), reply(409), reply(201));
    expect(await archiveReceipt(d, SHA, IMG)).toEqual({ ok: true, already: false });
    expect(d.calls).toHaveBeenCalledTimes(3);
  });

  it('retries a network failure, then gives up', async () => {
    const d = deps(...Array.from({ length: 6 }, () => new Error('offline')));
    expect(await archiveReceipt(d, SHA, IMG)).toEqual({ ok: false, detail: 'offline' });
    expect(d.calls).toHaveBeenCalledTimes(6);
  });

  it('does not retry a refusal (401)', async () => {
    const d = deps(reply(401, 'bad credentials'));
    expect(await archiveReceipt(d, SHA, IMG)).toEqual({ ok: false, detail: '401 bad credentials' });
    expect(d.calls).toHaveBeenCalledTimes(1);
  });

  it('refuses a digest that is not a sha256 without calling GitHub', async () => {
    const d = deps();
    expect(await archiveReceipt(d, '../x', IMG)).toMatchObject({ ok: false });
    expect(d.calls).not.toHaveBeenCalled();
  });
});

describe('fetchReceipt', () => {
  it('returns the raw bytes from the receipts branch', async () => {
    const d = deps(new Response(new Uint8Array([1, 2, 3]), { status: 200 }));
    expect(Array.from((await fetchReceipt(d, SHA))!)).toEqual([1, 2, 3]);
    const [url, init] = d.calls.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toContain(`receipts/${SHA}.jpg?ref=${RECEIPTS_BRANCH}`);
    expect((init.headers as Record<string, string>).Accept).toBe('application/vnd.github.raw');
  });

  it('is null when no copy was kept', async () => {
    expect(await fetchReceipt(deps(reply(404)), SHA)).toBeNull();
  });

  it('throws on other failures', async () => {
    await expect(fetchReceipt(deps(reply(500)), SHA)).rejects.toThrow('500');
  });

  it('never asks GitHub for a path that is not a digest', async () => {
    const d = deps();
    expect(await fetchReceipt(d, '../../etc')).toBeNull();
    expect(d.calls).not.toHaveBeenCalled();
  });
});

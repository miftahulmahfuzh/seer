import { describe, expect, it, vi } from 'vitest';
import fixture from './fixtures/receipts.json';
import {
  MIN_REPAIR_BUDGET_MS,
  READ_MESSAGES,
  isReaderDown,
  readOrder,
  visionDeps,
  type ReadOrderDeps,
} from './readOrder';
import { VisionTokenFloorError, VisionTransportError, type VisionResult } from './vision';

const IMG = '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAA==';
const MU = fixture.receipts[1];

const result = (text: string, finishReason: string | null = 'stop'): VisionResult => ({
  text,
  promptTokens: 2_400,
  completionTokens: 250,
  floor: 1_450,
  finishReason,
  raw: { text },
});

/** Fake calls and a clock that moves only when a test says so. */
function deps(primary: () => Promise<VisionResult>, repair?: () => Promise<VisionResult>, clock = { t: 0 }) {
  const d: ReadOrderDeps = {
    callPrimary: vi.fn(primary),
    callRepair: vi.fn(repair ?? (() => Promise.reject(new Error('repair not expected')))),
    now: () => clock.t,
  };
  return d;
}

describe('readOrder', () => {
  it('returns the order on a clean first read', async () => {
    const d = deps(() => Promise.resolve(result(JSON.stringify(MU.raw))));
    const out = await readOrder(d, IMG);
    expect(out).toEqual({ ok: true, order: MU.expected, raw: MU.raw, attempts: 1, promptTokens: 2_400, floor: 1_450 });
    expect(d.callRepair).not.toHaveBeenCalled();
  });

  it('repairs once, with the image and the issues, when the numbers do not add up', async () => {
    const bad = { ...MU.raw, total: '$28.30' };
    const d = deps(
      () => Promise.resolve(result(JSON.stringify(bad))),
      () => Promise.resolve(result(JSON.stringify(MU.raw))),
    );
    const out = await readOrder(d, IMG);
    expect(out.ok && out.attempts).toBe(2);
    expect(out.ok && out.order).toEqual(MU.expected);
    const [image, input] = vi.mocked(d.callRepair).mock.calls[0];
    expect(image).toBe(IMG);
    expect(input.malformedText).toBe(JSON.stringify(bad));
    expect(input.issues).toBe(
      '- Total $28.30 should equal the trade amount $27.90 plus the fees $0.13, which is $28.03.',
    );
  });

  it('repairs a reply with no JSON in it, and says so to the model only', async () => {
    const d = deps(
      () => Promise.resolve(result('I cannot help with that.')),
      () => Promise.resolve(result('still nothing')),
    );
    const out = await readOrder(d, IMG);
    expect(vi.mocked(d.callRepair).mock.calls[0][1].issues).toContain('no JSON object');
    expect(out).toMatchObject({ ok: false, code: 'unreadable', attempts: 2, message: READ_MESSAGES.unreadable });
  });

  it('gives up after one repair and shows the owner the first problem', async () => {
    const bad = { ...MU.raw, total: '$28.30' };
    const d = deps(
      () => Promise.resolve(result(JSON.stringify(bad))),
      () => Promise.resolve(result(JSON.stringify(bad))),
    );
    const out = await readOrder(d, IMG);
    expect(out).toMatchObject({
      ok: false,
      code: 'unreadable',
      attempts: 2,
      raw: bad,
      message: `${READ_MESSAGES.unreadable} Total $28.30 should equal the trade amount $27.90 plus the fees $0.13, which is $28.03.`,
    });
    expect(d.callRepair).toHaveBeenCalledOnce();
  });

  it('never repairs a token-floor trip', async () => {
    const d = deps(() => Promise.reject(new VisionTokenFloorError(900, 1_450, 1)));
    const out = await readOrder(d, IMG);
    expect(out).toMatchObject({ ok: false, code: 'token_floor', promptTokens: 900, floor: 1_450, attempts: 1 });
    expect(out.ok === false && out.message).toBe(READ_MESSAGES.token_floor);
    expect(d.callRepair).not.toHaveBeenCalled();
  });

  it('tells a timeout from an unreachable reader', async () => {
    const timeout = Object.assign(new Error('t'), { name: 'TimeoutError' });
    const a = await readOrder(deps(() => Promise.reject(new VisionTransportError('x', timeout))), IMG);
    const b = await readOrder(deps(() => Promise.reject(new VisionTransportError('x', new TypeError('fetch failed')))), IMG);
    expect(a).toMatchObject({ ok: false, code: 'timeout' });
    expect(b).toMatchObject({ ok: false, code: 'transport' });
  });

  it('does not repair a true answer: not an order summary, or not filled', async () => {
    const notOrder = deps(() => Promise.resolve(result('{"isOrderSummary": false}')));
    expect(await readOrder(notOrder, IMG)).toMatchObject({
      ok: false,
      code: 'not_order',
      message: READ_MESSAGES.not_order,
    });
    const cancelled = deps(() => Promise.resolve(result(JSON.stringify({ ...MU.raw, status: 'Cancelled' }))));
    expect(await readOrder(cancelled, IMG)).toMatchObject({
      ok: false,
      code: 'not_filled',
      message: 'Sean only records filled orders. This order says "Cancelled", not "Filled".',
    });
    expect(notOrder.callRepair).not.toHaveBeenCalled();
    expect(cancelled.callRepair).not.toHaveBeenCalled();
  });

  it('does not repair a reply cut off by max_tokens', async () => {
    const d = deps(() => Promise.resolve(result('{"ticker": "MU", "tot', 'length')));
    expect(await readOrder(d, IMG)).toMatchObject({ ok: false, code: 'unreadable', attempts: 1 });
    expect(d.callRepair).not.toHaveBeenCalled();
  });

  it('skips the repair when the first call ate the budget', async () => {
    const clock = { t: 0 };
    const d = deps(
      async () => {
        clock.t = 50_000 - MIN_REPAIR_BUDGET_MS + 1;
        return result(JSON.stringify({ ...MU.raw, total: '$28.30' }));
      },
      undefined,
      clock,
    );
    expect(await readOrder(d, IMG, 50_000)).toMatchObject({ ok: false, code: 'unreadable', attempts: 1 });
    expect(d.callRepair).not.toHaveBeenCalled();
  });

  it('gives the repair only the time that is left', async () => {
    const clock = { t: 0 };
    const d = deps(
      async () => {
        clock.t = 30_000;
        return result(JSON.stringify({ ...MU.raw, total: '$28.30' }));
      },
      () => Promise.resolve(result(JSON.stringify(MU.raw))),
      clock,
    );
    await readOrder(d, IMG, 50_000);
    expect(vi.mocked(d.callRepair).mock.calls[0][2]).toEqual({ timeoutMs: 20_000 });
  });

  it('reports a failed repair call by its own code', async () => {
    const d = deps(
      () => Promise.resolve(result(JSON.stringify({ ...MU.raw, total: '$28.30' }))),
      () => Promise.reject(new VisionTransportError('down')),
    );
    expect(await readOrder(d, IMG)).toMatchObject({ ok: false, code: 'transport', attempts: 2 });
  });

  it('rethrows an error that is not the vision client’s', async () => {
    await expect(readOrder(deps(() => Promise.reject(new RangeError('bug'))), IMG)).rejects.toThrow(RangeError);
  });
});

describe('isReaderDown', () => {
  it('splits reader failures (502) from picture failures (422)', () => {
    expect(['token_floor', 'timeout', 'transport'].every(c => isReaderDown(c as never))).toBe(true);
    expect(['not_order', 'not_filled', 'unreadable'].some(c => isReaderDown(c as never))).toBe(false);
  });
});

describe('visionDeps', () => {
  it('wires the real calls to the injected fetch', async () => {
    const doFetch = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          choices: [{ message: { content: JSON.stringify(MU.raw) }, finish_reason: 'stop' }],
          usage: { prompt_tokens: 3_000, completion_tokens: 250 },
        }),
        { status: 200 },
      ),
    );
    const out = await readOrder(
      visionDeps({ baseUrl: 'https://example.test/v4', apiKey: 'k', model: 'glm-4.6v' }, doFetch),
      IMG,
    );
    expect(out.ok && out.order).toEqual(MU.expected);
    expect(doFetch.mock.calls[0][0]).toBe('https://example.test/v4/chat/completions');
  });
});

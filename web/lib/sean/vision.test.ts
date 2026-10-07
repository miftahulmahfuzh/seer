import { describe, expect, it, vi } from 'vitest';
import { ORDER_SHAPE, ORDER_SYSTEM_PROMPT, buildOrderUserContent } from './prompt';
import {
  FLOOR_CHARS_PER_TOKEN,
  TOKEN_FLOOR_PER_IMAGE,
  VisionTokenFloorError,
  VisionTransportError,
  readOrderWithFetch,
  repairOrderWithFetch,
  tokenFloor,
  visionConfigFromEnv,
  type VisionConfig,
} from './vision';

// No network anywhere in this file: every case injects `fetch`.

const CFG: VisionConfig = { baseUrl: 'https://api.z.ai/api/coding/paas/v4', apiKey: 'test-key', model: 'glm-4.6v' };
const IMG = '/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAA==';

/** What the primary request's text costs at the floor's pessimistic 3 characters per token. */
const PRIMARY_TEXT_CHARS =
  ORDER_SYSTEM_PROMPT.length +
  buildOrderUserContent(IMG).reduce((n, p) => n + (p.type === 'text' ? p.text.length : 0), 0);
const PRIMARY_FLOOR = Math.ceil(PRIMARY_TEXT_CHARS / FLOOR_CHARS_PER_TOKEN) + TOKEN_FLOOR_PER_IMAGE;

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

function fakeFetch(body: unknown, status = 200) {
  return vi.fn<typeof fetch>().mockResolvedValue(jsonResponse(body, status));
}

const reply = (content: string, promptTokens: number) => ({
  choices: [{ message: { content }, finish_reason: 'stop' }],
  usage: { prompt_tokens: promptTokens, completion_tokens: 250 },
});

/** A dropped image: the endpoint counts only our text (~chars / 4) and invents a receipt. */
const DROPPED = reply('{"ticker":"AAPL","total":"$5.00"}', Math.ceil(PRIMARY_TEXT_CHARS / 4));

describe('the request', () => {
  it('copies run-insights transport: URL, bearer key, model, thinking disabled, data-URI image', async () => {
    const doFetch = fakeFetch(reply('{}', 2400));
    await readOrderWithFetch(doFetch, IMG, CFG, { timeoutMs: 5_000 });

    expect(doFetch).toHaveBeenCalledOnce();
    const [url, init] = doFetch.mock.calls[0];
    expect(url).toBe('https://api.z.ai/api/coding/paas/v4/chat/completions');
    expect(init?.method).toBe('POST');
    expect((init?.headers as Record<string, string>).Authorization).toBe('Bearer test-key');
    const body = JSON.parse(String(init?.body));
    expect(body.model).toBe('glm-4.6v');
    expect(body.thinking).toEqual({ type: 'disabled' });
    expect(body.response_format).toBeUndefined();
    expect(body.messages[0]).toEqual({ role: 'system', content: ORDER_SYSTEM_PROMPT });
    const parts = body.messages[1].content;
    expect(parts.filter((p: { type: string }) => p.type === 'image_url')).toEqual([
      { type: 'image_url', image_url: { url: `data:image/jpeg;base64,${IMG}` } },
    ]);
    expect(parts.at(-1).text).toContain(ORDER_SHAPE);
  });

  it('keeps a data: prefix the caller already added', () => {
    const parts = buildOrderUserContent(`data:image/jpeg;base64,${IMG}`);
    expect(parts[1]).toEqual({ type: 'image_url', image_url: { url: `data:image/jpeg;base64,${IMG}` } });
  });

  it('repairs in the same conversation, with the image, the first reply and the problems', async () => {
    const doFetch = fakeFetch(reply('{}', 2600));
    await repairOrderWithFetch(doFetch, IMG, CFG, { malformedText: '{"ticker":"MU"}', issues: '- Total is missing.' }, { timeoutMs: 5_000 });
    const body = JSON.parse(String(doFetch.mock.calls[0][1]?.body));
    expect(body.messages.map((m: { role: string }) => m.role)).toEqual(['system', 'user', 'assistant', 'user']);
    expect(body.messages[1].content.some((p: { type: string }) => p.type === 'image_url')).toBe(true);
    expect(body.messages[2].content).toBe('{"ticker":"MU"}');
    expect(body.messages[3].content).toContain('- Total is missing.');
  });
});

describe('the token floor', () => {
  it('is the text we sent at 3 characters a token plus 150 per image', () => {
    expect(tokenFloor([{ role: 'system', content: 'x'.repeat(300) }], 1)).toBe(100 + TOKEN_FLOOR_PER_IMAGE);
    expect(tokenFloor([{ role: 'system', content: 'x'.repeat(300) }], 0)).toBe(0);
  });

  it('refuses a dropped image even though the text alone clears a flat 500', async () => {
    expect(DROPPED.usage.prompt_tokens).toBeGreaterThan(500);
    const doFetch = fakeFetch(DROPPED);
    const error = await readOrderWithFetch(doFetch, IMG, CFG, { timeoutMs: 5_000 }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(VisionTokenFloorError);
    expect((error as VisionTokenFloorError).floor).toBe(PRIMARY_FLOOR);
    expect((error as VisionTokenFloorError).message).toContain(String(PRIMARY_FLOOR));
  });

  it('passes a delivered receipt image (text plus ~1,000 image tokens)', async () => {
    const real = Math.ceil(PRIMARY_TEXT_CHARS / 4) + 1_000;
    const doFetch = fakeFetch(reply('{"ticker":"MU"}', real));
    const result = await readOrderWithFetch(doFetch, IMG, CFG, { timeoutMs: 5_000 });
    expect(result.text).toBe('{"ticker":"MU"}');
    expect(result.promptTokens).toBe(real);
    expect(result.floor).toBe(PRIMARY_FLOOR);
  });

  it('treats a missing usage block as zero', async () => {
    const doFetch = fakeFetch({ choices: [{ message: { content: '{}' } }] });
    await expect(readOrderWithFetch(doFetch, IMG, CFG, { timeoutMs: 5_000 })).rejects.toThrow(VisionTokenFloorError);
  });

  it('checks the floor before the HTTP status (the measured drop was a 200)', async () => {
    const doFetch = fakeFetch({ error: 'bad' }, 500);
    await expect(readOrderWithFetch(doFetch, IMG, CFG, { timeoutMs: 5_000 })).rejects.toThrow(VisionTokenFloorError);
  });

  it('floors the repair too, because it carries the image again', async () => {
    const doFetch = fakeFetch(DROPPED);
    await expect(
      repairOrderWithFetch(doFetch, IMG, CFG, { malformedText: '{}', issues: '- x' }, { timeoutMs: 5_000 }),
    ).rejects.toThrow(VisionTokenFloorError);
  });
});

describe('transport errors', () => {
  it('wraps a non-200 that cleared the floor', async () => {
    const doFetch = fakeFetch({ error: { message: 'rate limited' }, usage: { prompt_tokens: 5_000 } }, 429);
    const error = await readOrderWithFetch(doFetch, IMG, CFG, { timeoutMs: 5_000 }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(VisionTransportError);
    expect((error as Error).message).toContain('429');
  });

  it('wraps a network failure and keeps the cause', async () => {
    const cause = Object.assign(new Error('timed out'), { name: 'TimeoutError' });
    const doFetch = vi.fn<typeof fetch>().mockRejectedValue(cause);
    const error = await readOrderWithFetch(doFetch, IMG, CFG, { timeoutMs: 5_000 }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(VisionTransportError);
    expect((error as VisionTransportError).detail).toBe(cause);
  });

  it('wraps a body that is not JSON', async () => {
    const doFetch = vi.fn<typeof fetch>().mockResolvedValue(new Response('<html>', { status: 502 }));
    await expect(readOrderWithFetch(doFetch, IMG, CFG, { timeoutMs: 5_000 })).rejects.toThrow(VisionTransportError);
  });
});

describe('visionConfigFromEnv', () => {
  const env = { LLM_API_KEY: 'k', LLM_VISION_BASE_URL: 'https://api.z.ai/api/coding/paas/v4/', LLM_VISION_MODEL: 'glm-4.6v' };

  it('reads the three variables and drops a trailing slash', () => {
    expect(visionConfigFromEnv(env)).toEqual({ apiKey: 'k', baseUrl: 'https://api.z.ai/api/coding/paas/v4', model: 'glm-4.6v' });
  });
  it('is null when one is missing', () => {
    expect(visionConfigFromEnv({ ...env, LLM_API_KEY: '' })).toBeNull();
    expect(visionConfigFromEnv({ ...env, LLM_VISION_MODEL: undefined })).toBeNull();
  });
  it('refuses the Anthropic-shaped endpoint that silently drops images', () => {
    expect(visionConfigFromEnv({ ...env, LLM_VISION_BASE_URL: 'https://api.z.ai/api/anthropic' })).toBeNull();
    expect(visionConfigFromEnv({ ...env, LLM_VISION_BASE_URL: 'https://api.z.ai/api/anthropic/v1' })).toBeNull();
  });
});

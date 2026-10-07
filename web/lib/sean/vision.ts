/**
 * The glm-4.6v client for Sean's screenshot reader. One `fetch`, no SDK, copied from the measured
 * transport in ~/run-insights lib/llm/vision.ts:
 *
 *   POST {LLM_VISION_BASE_URL}/chat/completions, Authorization: Bearer LLM_API_KEY,
 *   { model: LLM_VISION_MODEL, max_tokens, thinking: { type: 'disabled' }, messages },
 *   the image as an OpenAI-shaped { type: 'image_url', image_url: { url: 'data:image/jpeg;base64,...' } }.
 *
 * NEVER point it at z.ai's /api/anthropic base URL: that endpoint answers HTTP 200, silently drops
 * the image, and returns invented numbers (run-insights IMPLEMENTATION_PLAN.md §1.1).
 * visionConfigFromEnv refuses such a URL.
 *
 * Pure apart from `fetch`, which every function takes as an argument: the config is passed in
 * rather than read from a server env module, so vitest and the smoke script call it directly.
 * The route that uses it (Phase 2) is the server-only part.
 */
import { ORDER_SYSTEM_PROMPT, buildOrderUserContent, buildRepairNote, type VisionContentPart } from './prompt';

export type VisionConfig = { baseUrl: string; apiKey: string; model: string };

/**
 * The reader's settings from the environment (LLM_API_KEY, LLM_VISION_BASE_URL,
 * LLM_VISION_MODEL), or null when one is missing or the base URL is the Anthropic-shaped one.
 */
export function visionConfigFromEnv(env: Record<string, string | undefined> = process.env): VisionConfig | null {
  const apiKey = env.LLM_API_KEY?.trim();
  const baseUrl = env.LLM_VISION_BASE_URL?.trim().replace(/\/+$/, '');
  const model = env.LLM_VISION_MODEL?.trim();
  if (!apiKey || !baseUrl || !model) return null;
  if (/\/anthropic(\/|$)/i.test(baseUrl)) return null;
  return { baseUrl, apiKey, model };
}

/**
 * THE TOKEN FLOOR. A request whose response reports fewer prompt tokens than this cannot have
 * delivered its image, and its text is not read.
 *
 * TEXT-AWARE, like run-insights' Nina floor (lib/nina/vision.ts), not flat like its F04 floor of
 * 500 x images. prompt_tokens counts the system prompt and the shape too -- about 3,000
 * characters here -- so a dropped image would still report several hundred tokens of text, and a
 * flat floor sized for the image alone would have to guess that number. So the floor is the text
 * we actually sent, estimated at a deliberately pessimistic 3 characters per token (real BPE runs
 * nearer 4, which raises the floor: it errs toward "the reader could not see it", never toward
 * believing an invented receipt), PLUS a per-image term.
 *
 * Per image: 150, Nina's re-calibrated number. With the text already covered, the per-image term
 * only has to be positive -- a dropped image adds zero image tokens -- and a big one outlaws real
 * small images (Nina's 500 refused a delivered 612x862 card).
 *
 * MEASURED 2026-10-07 with web/scripts/sean-vision-smoke.mjs on all 30 of the owner's receipts
 * (739x1600 JPEGs sent as is): prompt_tokens = 2,351 for every one, floor 1,141, so a delivered
 * image clears the floor by 1,210 tokens, and the ~1,400 image tokens are what a dropped image
 * would lose -- the text alone (~990 tokens at 3 characters each, fewer in reality) stays below
 * 1,141. 30/30 read and matched the hand-checked transcription on the first try.
 *
 * MULTIPLIED by the image count. A text-only request (imageCount 0) is not floored at all.
 */
export const TOKEN_FLOOR_PER_IMAGE = 150;
export const FLOOR_CHARS_PER_TOKEN = 3;

/** The reply is ~250 tokens of JSON; 2048 leaves room for chatter without truncating. */
export const MAX_TOKENS = 2048;

type Message =
  | { role: 'system'; content: string }
  | { role: 'user'; content: string | VisionContentPart[] }
  | { role: 'assistant'; content: string };

/** prompt_tokens a response must report for this request to count as delivered. */
export function tokenFloor(messages: Message[], imageCount: number): number {
  if (imageCount <= 0) return 0;
  let chars = 0;
  for (const m of messages) {
    if (typeof m.content === 'string') chars += m.content.length;
    else for (const part of m.content) if (part.type === 'text') chars += part.text.length;
  }
  return Math.ceil(chars / FLOOR_CHARS_PER_TOKEN) + TOKEN_FLOOR_PER_IMAGE * imageCount;
}

/**
 * The floor tripped: the image cannot have reached the model. Never repaired -- a repair would
 * send the same request shape to the same misbehaving endpoint.
 */
export class VisionTokenFloorError extends Error {
  constructor(
    readonly promptTokens: number,
    readonly floor: number,
    readonly imageCount: number,
  ) {
    super(
      `vision response reported prompt_tokens=${promptTokens} for ${imageCount} image(s); ` +
        `expected >= ${floor}. The endpoint may have dropped the image -- refusing to read a ` +
        `response that may have invented its numbers.`,
    );
    this.name = 'VisionTokenFloorError';
  }
}

/** Network failure, timeout, a body that is not JSON, or a non-200 that cleared the floor. */
export class VisionTransportError extends Error {
  constructor(
    message: string,
    readonly detail?: unknown,
  ) {
    super(message);
    this.name = 'VisionTransportError';
  }
}

export type VisionResult = {
  text: string;
  promptTokens: number;
  completionTokens: number;
  /** The floor this response had to clear (0 for a text-only request). */
  floor: number;
  finishReason: string | null;
  /** The vendor's body, untouched. */
  raw: unknown;
};

type FetchLike = typeof fetch;

/** The injectable core: one POST, the floor, then the text. */
export async function callVisionWithFetch(
  fetchImpl: FetchLike,
  cfg: VisionConfig,
  messages: Message[],
  opts: { timeoutMs: number; imageCount: number },
): Promise<VisionResult> {
  const floor = tokenFloor(messages, opts.imageCount);

  let res: Response;
  try {
    res = await fetchImpl(`${cfg.baseUrl}/chat/completions`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${cfg.apiKey}` },
      body: JSON.stringify({
        model: cfg.model,
        max_tokens: MAX_TOKENS,
        // MEASURED in run-insights: thinking doubles latency (73 s vs 33.7 s) for an identical
        // score. Never remove.
        thinking: { type: 'disabled' },
        messages,
      }),
      signal: AbortSignal.timeout(opts.timeoutMs),
    });
  } catch (cause) {
    throw new VisionTransportError('vision request failed or timed out', cause);
  }

  let json: unknown;
  try {
    json = await res.json();
  } catch (cause) {
    throw new VisionTransportError(`vision response (HTTP ${res.status}) was not valid JSON`, cause);
  }

  const body = json as {
    usage?: { prompt_tokens?: number; completion_tokens?: number };
    choices?: Array<{ message?: { content?: string }; finish_reason?: string }>;
  };
  const promptTokens = body.usage?.prompt_tokens ?? 0;
  const completionTokens = body.usage?.completion_tokens ?? 0;

  // THE GUARD sits above every read of `choices`: nothing downstream may see the text of a
  // response that fails it, because that text is exactly where invented numbers live. A missing
  // usage block counts as 0 and fails closed. Checked before res.ok on purpose: the measured
  // failure was itself an HTTP 200.
  if (promptTokens < floor) {
    throw new VisionTokenFloorError(promptTokens, floor, opts.imageCount);
  }

  if (!res.ok) {
    throw new VisionTransportError(`vision endpoint returned ${res.status}: ${JSON.stringify(json).slice(0, 300)}`);
  }

  const choice = body.choices?.[0];
  return {
    text: choice?.message?.content ?? '',
    promptTokens,
    completionTokens,
    floor,
    finishReason: choice?.finish_reason ?? null,
    raw: json,
  };
}

/** The first read of one receipt. `imageB64` is bare base64 JPEG (a data: prefix is tolerated). */
export function readOrderWithFetch(
  fetchImpl: FetchLike,
  imageB64: string,
  cfg: VisionConfig,
  opts: { timeoutMs: number },
): Promise<VisionResult> {
  return callVisionWithFetch(
    fetchImpl,
    cfg,
    [
      { role: 'system', content: ORDER_SYSTEM_PROMPT },
      { role: 'user', content: buildOrderUserContent(imageB64) },
    ],
    { timeoutMs: opts.timeoutMs, imageCount: 1 },
  );
}

/**
 * The one repair: the same conversation (image included, so the floor applies again), the
 * model's first reply, and the list of problems the checks found.
 */
export function repairOrderWithFetch(
  fetchImpl: FetchLike,
  imageB64: string,
  cfg: VisionConfig,
  input: { malformedText: string; issues: string },
  opts: { timeoutMs: number },
): Promise<VisionResult> {
  return callVisionWithFetch(
    fetchImpl,
    cfg,
    [
      { role: 'system', content: ORDER_SYSTEM_PROMPT },
      { role: 'user', content: buildOrderUserContent(imageB64) },
      { role: 'assistant', content: input.malformedText },
      { role: 'user', content: buildRepairNote(input.issues) },
    ],
    { timeoutMs: opts.timeoutMs, imageCount: 1 },
  );
}

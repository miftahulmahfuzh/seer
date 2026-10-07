/**
 * One screenshot -> one checked order: vision call -> JSON -> toOrder -> at most one repair.
 *
 * THE CONTRACT (run-insights lib/llm/extract.ts): this never throws for a model problem. Every
 * failure comes back as `{ ok: false, code, message }` with a plain-words message the Trades page
 * can show as is. It re-throws only an error that is not one of the vision client's own.
 *
 * Which failures get the one repair: only "unreadable" -- the reply was not JSON, a field could
 * not be parsed, or the numbers did not add up. Never the token floor (the same request to the
 * same endpoint fails the same way), never a timeout or transport error, never "not an order
 * summary" or "not filled" (those are true answers, not misreads), never a reply cut off by
 * max_tokens, and never when the time left is too short for a second call.
 *
 * The calls and the clock are injected (ReadOrderDeps), so the whole flow is unit-tested with no
 * network and no timers. Production builds them with visionDeps(cfg).
 */
import { extractJsonObject } from './extractJson';
import { toOrder, type ToOrderResult } from './order';
import type { SeanOrder } from './types';
import {
  VisionTokenFloorError,
  VisionTransportError,
  readOrderWithFetch,
  repairOrderWithFetch,
  type VisionConfig,
  type VisionResult,
} from './vision';

/** The whole read must finish inside the route's 60 s maxDuration, with room to write the row. */
export const READ_BUDGET_MS = 55_000;
export const PRIMARY_TIMEOUT_MS = 40_000;
export const REPAIR_TIMEOUT_MS = 30_000;
/** A repair is skipped when less than this is left: one receipt took 4.7-10.5 s (30 measured). */
export const MIN_REPAIR_BUDGET_MS = 12_000;

export type ReadOrderDeps = {
  callPrimary: (imageB64: string, opts: { timeoutMs: number }) => Promise<VisionResult>;
  callRepair: (
    imageB64: string,
    input: { malformedText: string; issues: string },
    opts: { timeoutMs: number },
  ) => Promise<VisionResult>;
  now: () => number;
};

/** The production wiring: the real glm-4.6v calls with `cfg`, the real clock. */
export function visionDeps(cfg: VisionConfig, fetchImpl: typeof fetch = (input, init) => fetch(input, init)): ReadOrderDeps {
  return {
    callPrimary: (imageB64, opts) => readOrderWithFetch(fetchImpl, imageB64, cfg, opts),
    callRepair: (imageB64, input, opts) => repairOrderWithFetch(fetchImpl, imageB64, cfg, input, opts),
    now: () => Date.now(),
  };
}

export type ReadOrderCode = 'token_floor' | 'timeout' | 'transport' | 'not_order' | 'not_filled' | 'unreadable';

/** What the owner reads when a picture is refused. No ids, no jargon. */
export const READ_MESSAGES: Record<ReadOrderCode, string> = {
  token_floor: 'The reader could not see this picture. Try it again in a minute.',
  timeout: 'The reader took too long with this picture. Try it again.',
  transport: 'The reader could not be reached. Try again in a minute.',
  not_order: 'This picture is not a Gotrade order summary.',
  not_filled: 'Sean only records filled orders.',
  unreadable: 'Sean could not read this order summary clearly.',
};

/** The reader itself failed (HTTP 502 in the route), as opposed to the picture (HTTP 422). */
export function isReaderDown(code: ReadOrderCode): boolean {
  return code === 'token_floor' || code === 'timeout' || code === 'transport';
}

export type ReadOrderOutcome =
  | {
      ok: true;
      order: SeanOrder;
      /** The model's JSON that produced the order, for sean_orders.raw. */
      raw: unknown;
      attempts: 1 | 2;
      promptTokens: number;
      floor: number;
    }
  | {
      ok: false;
      code: ReadOrderCode;
      /** READ_MESSAGES[code], plus the first issue when there is one. */
      message: string;
      issues: string[];
      raw: unknown | null;
      attempts: 1 | 2;
      promptTokens: number | null;
      floor: number | null;
      /** For logs only, never shown: the vision error's own message when the reader failed. */
      detail: string | null;
    };

type Failure = Extract<ReadOrderOutcome, { ok: false }>;

/** Said to the model in the repair turn; never shown to the owner. */
const NO_JSON = 'The reply contained no JSON object at all. Return ONLY the JSON object.';

function failure(
  code: ReadOrderCode,
  issues: string[],
  raw: unknown | null,
  attempts: 1 | 2,
  tokens: { promptTokens: number | null; floor: number | null },
  detail: string | null = null,
): Failure {
  const shown = isReaderDown(code) || code === 'not_order' ? undefined : issues.find(i => i !== NO_JSON);
  const message = shown === undefined ? READ_MESSAGES[code] : `${READ_MESSAGES[code]} ${shown}`;
  return { ok: false, code, message, issues, raw, attempts, ...tokens, detail };
}

/** A thrown vision error -> its code; null means "not ours, rethrow". */
function codeForVisionError(cause: unknown): ReadOrderCode | null {
  if (cause instanceof VisionTokenFloorError) return 'token_floor';
  if (cause instanceof VisionTransportError) {
    const inner = cause.detail;
    const isTimeout = inner instanceof Error && (inner.name === 'TimeoutError' || inner.name === 'AbortError');
    return isTimeout ? 'timeout' : 'transport';
  }
  return null;
}

function detailOf(cause: unknown): string {
  const inner = cause instanceof VisionTransportError && cause.detail instanceof Error ? ` (${cause.detail.message})` : '';
  return `${cause instanceof Error ? cause.message : String(cause)}${inner}`;
}

function thrownTokens(cause: unknown): { promptTokens: number | null; floor: number | null } {
  return cause instanceof VisionTokenFloorError
    ? { promptTokens: cause.promptTokens, floor: cause.floor }
    : { promptTokens: null, floor: null };
}

export async function readOrder(
  deps: ReadOrderDeps,
  imageB64: string,
  budgetMs: number = READ_BUDGET_MS,
): Promise<ReadOrderOutcome> {
  const startedAt = deps.now();

  let primary: VisionResult;
  try {
    primary = await deps.callPrimary(imageB64, { timeoutMs: Math.min(PRIMARY_TIMEOUT_MS, budgetMs) });
  } catch (cause) {
    const code = codeForVisionError(cause);
    if (code === null) throw cause;
    return failure(code, [], null, 1, thrownTokens(cause), detailOf(cause));
  }

  const firstJson = extractJsonObject(primary.text);
  const first: ToOrderResult | null = firstJson === null ? null : toOrder(firstJson);
  const firstTokens = { promptTokens: primary.promptTokens, floor: primary.floor };

  if (first?.ok) {
    return { ok: true, order: first.order, raw: firstJson, attempts: 1, ...firstTokens };
  }
  if (first && first.kind !== 'unreadable') {
    return failure(first.kind, first.issues, firstJson, 1, firstTokens);
  }

  const firstIssues = first === null ? [NO_JSON] : first.issues;
  const budgetLeft = budgetMs - (deps.now() - startedAt);
  if (primary.finishReason === 'length' || budgetLeft < MIN_REPAIR_BUDGET_MS) {
    return failure('unreadable', firstIssues, firstJson, 1, firstTokens);
  }

  let repair: VisionResult;
  try {
    repair = await deps.callRepair(
      imageB64,
      { malformedText: primary.text, issues: firstIssues.map(i => `- ${i}`).join('\n') },
      { timeoutMs: Math.min(REPAIR_TIMEOUT_MS, budgetLeft) },
    );
  } catch (cause) {
    const code = codeForVisionError(cause);
    if (code === null) throw cause;
    return failure(code, firstIssues, firstJson, 2, thrownTokens(cause), detailOf(cause));
  }

  const secondJson = extractJsonObject(repair.text);
  const second: ToOrderResult | null = secondJson === null ? null : toOrder(secondJson);
  const secondTokens = { promptTokens: repair.promptTokens, floor: repair.floor };

  if (second?.ok) {
    return { ok: true, order: second.order, raw: secondJson, attempts: 2, ...secondTokens };
  }
  if (second === null) return failure('unreadable', [NO_JSON], firstJson, 2, secondTokens);
  return failure(second.kind, second.issues, secondJson, 2, secondTokens);
}

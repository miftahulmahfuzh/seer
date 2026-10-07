/**
 * Pull a JSON object out of whatever the model actually said.
 *
 * Ported verbatim from ~/run-insights lib/llm/extractJson.ts, which is proven against real
 * glm-4.6v output: strip a ```json fence if there is one, then take the FIRST `{` to the LAST `}`.
 * Chatter before or after the object is dropped by construction; nested braces survive because
 * the slice is outermost-to-outermost. Returns null -- never throws -- for no braces, malformed
 * JSON, or a value that is not a plain object, so readOrder treats "no object" and "an object
 * that failed the checks" the same way: both are repairable.
 */

const FENCE_RE = /```(?:json)?\s*([\s\S]*?)```/;

export function extractJsonObject(text: string | null | undefined): unknown | null {
  if (!text) return null;
  let s = text.trim();

  const fence = s.match(FENCE_RE);
  if (fence?.[1]) s = fence[1].trim();

  const open = s.indexOf('{');
  const close = s.lastIndexOf('}');
  if (open === -1 || close === -1 || close < open) return null;

  try {
    const parsed: unknown = JSON.parse(s.slice(open, close + 1));
    return parsed !== null && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

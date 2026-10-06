/**
 * "Why this pick": what a reason toggle shows, and how a stored `evidence` value is read.
 *
 * `evidence` (migration 009, written by the engine's paper step) is a JSON array of short
 * plain-English facts: the numbers the method used for that pick. The LLM's explanation is
 * written from those facts; when there is no explanation the facts themselves are the reason.
 */

/**
 * A stored `evidence` value as a list of facts, or null when there is nothing usable. Defensive on
 * purpose: anything that is not an array (NULL, a missing key before 009 is applied, an object, a
 * string) reads as null, non-string items are dropped, items are trimmed and blank ones dropped,
 * and an array left empty reads as null.
 */
export function parseEvidence(raw: unknown): string[] | null {
  if (!Array.isArray(raw)) return null;
  const facts = raw
    .filter((f): f is string => typeof f === 'string')
    .map(f => f.trim())
    .filter(f => f !== '');
  return facts.length > 0 ? facts : null;
}

export type Why =
  | { kind: 'text'; text: string }
  | { kind: 'facts'; facts: string[] }
  | { kind: 'missing'; text: string };

/**
 * What a reason toggle shows: the plain-language text when there is one; else the facts, as a
 * short list; else the `missing` line. Blank text counts as no text.
 */
export function whyContent(text: string | null | undefined, facts: readonly string[] | null | undefined, missing: string): Why {
  const t = (text ?? '').trim();
  if (t !== '') return { kind: 'text', text: t };
  const f = parseEvidence(facts);
  if (f) return { kind: 'facts', facts: f };
  return { kind: 'missing', text: missing };
}

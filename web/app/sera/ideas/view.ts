// Pure helpers for /sera/ideas. No data access; page.tsx feeds lab.methods and lab.ideasSeen.
import { SOURCE_KIND_LABEL } from '../../../lib/sera/glossary';
import type { LabMethod, LabSeen } from '../../../lib/sera/types';

/** Methods with one status, ordered by id (numeric-aware: M0002 before M0010). */
export function methodsWithStatus(methods: readonly LabMethod[], status: LabMethod['status']): LabMethod[] {
  return methods
    .filter(m => m.status === status)
    .sort((a, b) => a.id.localeCompare(b.id, 'en', { numeric: true }));
}

/** The data wishlist line for a blocked method. */
export function needs(blockedOn: string): string {
  const t = blockedOn.trim();
  return t ? `needs: ${t}` : 'needs: not written down yet';
}

export const sourceLabel = (kind: string): string =>
  (SOURCE_KIND_LABEL as Record<string, string>)[kind] ?? kind;

/** The source ref when it is an http(s) URL, else null. */
export function sourceLink(ref: string): string | null {
  const t = ref.trim();
  return /^https?:\/\//i.test(t) && urlParts(t).safe ? t : null;
}

/** Safe-to-link check plus short display text for a URL. */
export function urlParts(url: string): { safe: boolean; host: string; display: string } {
  try {
    const u = new URL(url);
    const safe = u.protocol === 'https:' || u.protocol === 'http:';
    const full = (u.host + u.pathname + u.search).replace(/\/$/, '');
    return { safe, host: u.host || url, display: full.length > 72 ? `${full.slice(0, 71)}…` : full };
  } catch {
    return { safe: false, host: url, display: url };
  }
}

export type ReadingLink = {
  key: string;
  url: string;
  safe: boolean;
  host: string;
  display: string;
  note: string;
  methodId: string | null;
  added: string;
};
export type Concept = { key: string; label: string; note: string };
export type ConceptGroup = { methodId: string | null; concepts: Concept[] };
export type ReadingList = { links: ReadingLink[]; groups: ConceptGroup[]; conceptCount: number };

/**
 * `url:` keys become links (newest first); every other key is a concept (the `concept:` prefix
 * is dropped), grouped by the method it led to (ids in numeric order, untied concepts last).
 */
export function readingList(seen: readonly LabSeen[]): ReadingList {
  const links: ReadingLink[] = [];
  const byMethod = new Map<string | null, Concept[]>();
  for (const it of seen) {
    if (it.key.startsWith('url:')) {
      const url = it.key.slice(4).trim();
      links.push({ key: it.key, url, ...urlParts(url), note: it.note, methodId: it.methodId, added: it.added });
      continue;
    }
    const label = it.key.startsWith('concept:') ? it.key.slice(8) : it.key;
    const list = byMethod.get(it.methodId) ?? [];
    list.push({ key: it.key, label, note: it.note });
    byMethod.set(it.methodId, list);
  }
  links.sort((a, b) => (a.added === b.added ? a.key.localeCompare(b.key) : a.added < b.added ? 1 : -1));
  const groups = [...byMethod.entries()]
    .map(([methodId, concepts]) => ({ methodId, concepts }))
    .sort((a, b) => {
      if (a.methodId === b.methodId) return 0;
      if (a.methodId === null) return 1;
      if (b.methodId === null) return -1;
      return a.methodId.localeCompare(b.methodId, 'en', { numeric: true });
    });
  return { links, groups, conceptCount: seen.length - links.length };
}

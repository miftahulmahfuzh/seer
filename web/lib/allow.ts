/** Seer is private to exactly one Google account. */
export function isAllowed(email: string | null | undefined, allowed: string | undefined): boolean {
  if (!email || !allowed) return false;
  return email.trim().toLowerCase() === allowed.trim().toLowerCase();
}

/**
 * A post-sign-in destination taken from `?next=`: only an internal path such as '/sera'.
 * Never '//host', '/\host', a backslash or a control character (open-redirect tricks). Anything else: `fallback`.
 */
export function safeNext(next: string | string[] | undefined, fallback = '/'): string {
  const v = Array.isArray(next) ? next[0] : next;
  if (!v || !v.startsWith('/') || v.startsWith('//') || v.startsWith('/\\')) return fallback;
  if (/[\u0000-\u001f\u007f\\]/.test(v)) return fallback;
  return v;
}

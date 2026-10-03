/** Seer is private to exactly one Google account. */
export function isAllowed(email: string | null | undefined, allowed: string | undefined): boolean {
  if (!email || !allowed) return false;
  return email.trim().toLowerCase() === allowed.trim().toLowerCase();
}

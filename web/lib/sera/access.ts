/** The one account that may see Sera (/sera). Sign-in itself is still limited by ALLOWED_EMAIL. */
export const SERA_EMAIL = 'mahfuzh74@gmail.com';

/** True only for SERA_EMAIL, compared trimmed and case-insensitively. */
export function isSeraUser(email: string | null | undefined): boolean {
  if (!email) return false;
  return email.trim().toLowerCase() === SERA_EMAIL;
}

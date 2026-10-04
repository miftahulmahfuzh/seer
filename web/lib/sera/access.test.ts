import { describe, expect, it } from 'vitest';
import { isSeraUser, SERA_EMAIL } from './access';

describe('isSeraUser', () => {
  it('is pinned to the owner address', () => {
    expect(SERA_EMAIL).toBe('mahfuzh74@gmail.com');
  });
  it('accepts the owner, trimmed and case-insensitively', () => {
    expect(isSeraUser('mahfuzh74@gmail.com')).toBe(true);
    expect(isSeraUser('  Mahfuzh74@Gmail.COM ')).toBe(true);
  });
  it('refuses everyone else and missing emails', () => {
    expect(isSeraUser('someone.else@gmail.com')).toBe(false);
    expect(isSeraUser('mahfuzh74@gmail.com.evil.io')).toBe(false);
    expect(isSeraUser('')).toBe(false);
    expect(isSeraUser(null)).toBe(false);
    expect(isSeraUser(undefined)).toBe(false);
  });
});

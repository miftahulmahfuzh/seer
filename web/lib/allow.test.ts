import { describe, expect, it } from 'vitest';
import { isAllowed } from './allow';

describe('isAllowed', () => {
  it('accepts only the configured email, case-insensitively', () => {
    expect(isAllowed('mahfuzh74@gmail.com', 'mahfuzh74@gmail.com')).toBe(true);
    expect(isAllowed('Mahfuzh74@Gmail.com', 'mahfuzh74@gmail.com')).toBe(true);
    expect(isAllowed('someone.else@gmail.com', 'mahfuzh74@gmail.com')).toBe(false);
  });
  it('rejects everyone when unconfigured or email missing', () => {
    expect(isAllowed('mahfuzh74@gmail.com', undefined)).toBe(false);
    expect(isAllowed('mahfuzh74@gmail.com', '')).toBe(false);
    expect(isAllowed(null, 'mahfuzh74@gmail.com')).toBe(false);
  });
});

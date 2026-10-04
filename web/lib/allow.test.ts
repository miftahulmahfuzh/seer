import { describe, expect, it } from 'vitest';
import { isAllowed, safeNext } from './allow';

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

describe('safeNext', () => {
  it('keeps internal paths, query included', () => {
    expect(safeNext('/sera')).toBe('/sera');
    expect(safeNext('/sera/methods/M0001?show=all')).toBe('/sera/methods/M0001?show=all');
    expect(safeNext(['/sera/journal', '/x'])).toBe('/sera/journal');
  });
  it('falls back on anything that could leave the site', () => {
    expect(safeNext(undefined)).toBe('/');
    expect(safeNext('')).toBe('/');
    expect(safeNext('sera')).toBe('/');
    expect(safeNext('https://evil.example')).toBe('/');
    expect(safeNext('//evil.example')).toBe('/');
    expect(safeNext('/\\evil.example')).toBe('/');
    expect(safeNext('/sera\\..\\x')).toBe('/');
    expect(safeNext('/sera\nSet-Cookie: x')).toBe('/');
  });
  it('uses the given fallback', () => {
    expect(safeNext('https://evil.example', '/sera')).toBe('/sera');
  });
});

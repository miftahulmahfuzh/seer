import { describe, expect, it } from 'vitest';
import { addDays, isStale, nextUsSession, wibDate, wibTime } from './session';

// Instants are given in UTC. In October, ET = UTC-4 and WIB = UTC+7.
describe('nextUsSession', () => {
  it('is today while the US session has not closed', () => {
    expect(nextUsSession(new Date('2026-10-07T14:00:00Z'))).toBe('2026-10-07'); // Wed 10:00 ET
  });
  it('rolls to the next weekday after the 16:00 ET close', () => {
    expect(nextUsSession(new Date('2026-10-07T20:30:00Z'))).toBe('2026-10-08'); // Wed 16:30 ET
  });
  it('skips the weekend', () => {
    expect(nextUsSession(new Date('2026-10-09T21:00:00Z'))).toBe('2026-10-12'); // Fri 17:00 ET
    expect(nextUsSession(new Date('2026-10-10T15:00:00Z'))).toBe('2026-10-12'); // Sat
    expect(nextUsSession(new Date('2026-10-11T15:00:00Z'))).toBe('2026-10-12'); // Sun
  });
  // 23:00 UTC was the old nightly slot; the real one is 06:17 UTC (13:17 WIB). Either way an
  // instant after the US close targets the next session.
  it('rolls to the next session for an instant after the close', () => {
    expect(nextUsSession(new Date('2026-10-06T23:00:00Z'))).toBe('2026-10-07'); // Tue 19:00 ET
  });
});

describe('isStale', () => {
  const now = new Date('2026-10-07T00:00:00Z'); // Wed 07:00 WIB, Tue 20:00 ET
  it('is stale with no successful run', () => {
    expect(isStale(null, now)).toBe(true);
  });
  it('is fresh when picks target the next session', () => {
    expect(isStale('2026-10-07', now)).toBe(false);
  });
  it('is fresh when picks target a later session (holiday skipped)', () => {
    expect(isStale('2026-10-08', now)).toBe(false);
  });
  it('is stale when picks target an earlier session', () => {
    expect(isStale('2026-10-06', now)).toBe(true);
  });
});

describe('wibDate', () => {
  it('uses the Jakarta calendar day', () => {
    expect(wibDate(new Date('2026-10-06T23:00:00Z'))).toBe('2026-10-07');
  });
});

describe('wibTime', () => {
  it('reads the three nightly slots in Jakarta, 24-hour', () => {
    expect(wibTime(new Date('2026-10-08T06:17:00Z'))).toBe('13:17');
    expect(wibTime(new Date('2026-10-08T09:41:00Z'))).toBe('16:41');
    expect(wibTime(new Date('2026-10-08T12:41:00Z'))).toBe('19:41');
  });
  it('is 00:00, not 24:00, at the WIB day boundary', () => {
    expect(wibTime(new Date('2026-10-07T17:00:00Z'))).toBe('00:00');
  });
});

describe('addDays', () => {
  it('steps the calendar forwards and backwards', () => {
    expect(addDays('2026-10-08', 1)).toBe('2026-10-09');
    expect(addDays('2026-10-12', -2)).toBe('2026-10-10');
    expect(addDays('2026-11-01', -1)).toBe('2026-10-31');
    expect(addDays('2027-03-01', -1)).toBe('2027-02-28');
  });
});

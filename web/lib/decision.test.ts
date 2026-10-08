import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';
import {
  NIGHTLY_DAYS_UTC, NIGHTLY_SLOTS_UTC, PAPER_PAUSED, panelState, pipelineState, publishDay, timing,
} from './decision';
import { wibDate, wibTime } from './session';

// The workflow is the source of truth for both the schedule and the switch; this module only
// mirrors them. Reading the file here is what turns a drift into a failing test rather than a page
// that quietly states the wrong hour.
const NIGHTLY = readFileSync(new URL('../../.github/workflows/nightly.yml', import.meta.url), 'utf8');

describe('nightly.yml is the source of truth', () => {
  it('mirrors every cron slot, in order', () => {
    const crons = [...NIGHTLY.matchAll(/^\s*- cron: '(\d+) (\d+) \* \* (\S+)'/gm)].map(m => m.slice(1));
    expect(crons).toHaveLength(NIGHTLY_SLOTS_UTC.length);
    expect(crons.map(([min, hour]) => [Number(hour), Number(min)]))
      .toEqual(NIGHTLY_SLOTS_UTC.map(s => [s[0], s[1]]));
    for (const c of crons) expect(c[2]).toBe('2-6');
  });

  it('reads cron 2-6 as Tuesday through Saturday', () => {
    expect(NIGHTLY_DAYS_UTC).toEqual([2, 3, 4, 5, 6]);
  });

  it('mirrors PAPER_PAUSED', () => {
    const m = NIGHTLY.match(/^\s*PAPER_PAUSED: '(true|false)'/m);
    expect(m).not.toBeNull();
    expect(PAPER_PAUSED).toBe(m![1] === 'true');
  });
});

describe('the slots in the time the owner reads', () => {
  const t = timing(new Date('2026-10-08T01:17:40Z'));
  it('is due at 13:17 WIB and late after 19:41 WIB', () => {
    expect(wibTime(t.dueAt)).toBe('13:17');
    expect(wibTime(t.lateAfter)).toBe('19:41');
  });
});

describe('publishDay', () => {
  it("is the session's own day from Tuesday to Friday", () => {
    expect(publishDay('2026-10-06')).toBe('2026-10-06'); // Tue
    expect(publishDay('2026-10-09')).toBe('2026-10-09'); // Fri
  });
  it("is the Saturday before for a Monday session", () => {
    expect(publishDay('2026-10-12')).toBe('2026-10-10'); // Mon <- Sat
  });
});

// 2026-10-08, 08:17 WIB. The page was blank and read as data loss; 80 book_targets rows, 4 orders
// and four pending decisions were untouched in the database, and the nightly was not due for
// another five hours. `lastGoodRun` is runs.id 10's real finished_at.
describe('the morning that produced this requirement', () => {
  const now = new Date('2026-10-08T01:17:40Z');
  const lastGoodRun = new Date('2026-10-07T13:30:28Z');

  it('knows nothing is wrong yet', () => {
    expect(pipelineState('2026-10-07', lastGoodRun, now)).toBe('waiting');
  });

  it('says when the next decision is due, in WIB', () => {
    const t = timing(now);
    expect(t.target).toBe('2026-10-08');
    expect(wibDate(t.dueAt)).toBe('2026-10-08');
    expect(wibTime(t.dueAt)).toBe('13:17');
  });

  it('calls the expired decision spent, not missing', () => {
    expect(panelState('2026-10-07', true, now)).toBe('spent');
  });

  it('calls an expired no-decision session spent too (C and SPY)', () => {
    expect(panelState('2026-10-07', false, now)).toBe('spent');
  });
});

describe('pipelineState', () => {
  it('is never before the first successful run', () => {
    expect(pipelineState(null, null, new Date('2026-10-08T01:00:00Z'))).toBe('never');
    expect(pipelineState('2026-10-07', null, new Date('2026-10-08T01:00:00Z'))).toBe('never');
  });

  it('is current while the last good run targets the coming session', () => {
    // Wed 10:00 ET: the session that is coming is still 2026-10-07.
    expect(pipelineState('2026-10-07', new Date('2026-10-07T13:30:28Z'), new Date('2026-10-07T14:00:00Z')))
      .toBe('current');
  });

  it('is late only once the last retry slot has fired', () => {
    const run = new Date('2026-10-07T13:30:28Z');
    expect(pipelineState('2026-10-07', run, new Date('2026-10-08T12:40:00Z'))).toBe('waiting');
    expect(pipelineState('2026-10-07', run, new Date('2026-10-08T12:41:00Z'))).toBe('late');
  });

  // The case a "a slot has fired since the last good run" rule gets wrong: at Monday's close the
  // target is Tuesday, and Tuesday's run has not come due yet.
  it('is not late on a Monday evening', () => {
    expect(pipelineState('2026-10-12', new Date('2026-10-10T06:30:00Z'), new Date('2026-10-12T21:00:00Z')))
      .toBe('waiting');
  });

  it('reads a Sunday against the Saturday run that owes Monday its picks', () => {
    const sunday = new Date('2026-10-11T03:00:00Z');
    expect(timing(sunday).target).toBe('2026-10-12');
    expect(wibTime(timing(sunday).dueAt)).toBe('13:17');
    // Saturday delivered Monday's picks: nothing is wrong.
    expect(pipelineState('2026-10-12', new Date('2026-10-10T06:30:00Z'), sunday)).toBe('current');
    // Saturday never ran: by Sunday that is late, not a wait.
    expect(pipelineState('2026-10-09', new Date('2026-10-09T06:30:00Z'), sunday)).toBe('late');
  });

  // After the US clocks change, nextUsSession still rolls at the 16:00 ET close.
  it('holds across the daylight-saving change', () => {
    expect(timing(new Date('2026-11-09T22:00:00Z')).target).toBe('2026-11-10');
    expect(wibTime(timing(new Date('2026-11-09T22:00:00Z')).dueAt)).toBe('13:17');
  });
});

describe('panelState', () => {
  const now = new Date('2026-10-08T01:17:40Z'); // target 2026-10-08

  it('is never while paper has not started for the strategy', () => {
    expect(panelState(null, false, now)).toBe('never');
  });

  it('never calls a retired strategy live, even on a decision for the coming session', () => {
    // D9.6: phase 12 retires six entries and leaves their pending rows in place (invariant 3).
    // A predecessor retired on the night its successor started holds a `pending_session` for the
    // COMING session with `pending_decision = true` -- the one shape where the date test alone
    // would say `live`. It is a record, and it must read as one.
    const now = new Date('2026-10-08T01:17:40Z');   // target 2026-10-08
    expect(panelState('2026-10-08', true, now)).toBe('live');              // active: an instruction
    expect(panelState('2026-10-08', true, now, true)).toBe('spent');       // retired: a record
    expect(panelState('2026-10-07', true, now, true)).toBe('spent');       // and the common case
    expect(panelState(null, false, now, true)).toBe('never');              // never started, retired
    // The flag defaults off, so every existing call keeps its meaning.
    expect(panelState('2026-10-08', true, now, false)).toBe(panelState('2026-10-08', true, now));
  });

  it('is live when the decision is for the session that is coming', () => {
    expect(panelState('2026-10-08', true, now)).toBe('live');
    expect(panelState('2026-10-09', true, now)).toBe('live');
  });

  // The common case: roughly three weeks in four for a monthly book. The engine wrote the answer;
  // this module does not recompute the month and week boundaries.
  it('is holding when the coming session is not a decision session', () => {
    expect(panelState('2026-10-08', false, now)).toBe('holding');
  });
});

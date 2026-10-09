import { describe, expect, it } from 'vitest';
import { emptyNote, fillVerb, FILL_REASON, historyHref, type EmptyStrategy, type EmptyWhat } from './history';

const MOM: EmptyStrategy = { name: 'MOM · Regime momentum', rulesId: 'monthly-hold-frac-gotrade', paperStart: '2026-10-07' };
const RMW: EmptyStrategy = { name: 'RMW · Braked momentum', rulesId: 'monthly-rank-weekly-resize-frac-gotrade', paperStart: '2026-10-07' };
const C: EmptyStrategy = { name: 'C · News veto', rulesId: 'design-v0-gotrade', paperStart: '2026-10-07' };

const note = (what: EmptyWhat, strategy = MOM, outcome: 'all' | 'win' | 'loss' = 'all') =>
  emptyNote({ what, strategy, outcome });

describe('emptyNote: why the list is empty, in the words that are true', () => {
  it('names the cadence instead of blaming the filters', () => {
    // The 2026-10-09 report: "the paper trade clearly started on 7th october, but why can't we
    // see any history yet?" The page said "No trades match these filters", which points at the
    // only thing that was NOT the reason.
    const n = note('trades');
    expect(n.title).toBe('Nothing sold yet');
    expect(n.sub).toContain('first session of each month');
    expect(n.sub).not.toContain('filter');
  });

  it('tells a weekly-resize book apart from a hold-all-month one', () => {
    expect(note('trades', RMW).sub).toContain('checks the sizes weekly');
    expect(note('trades', MOM).sub).not.toContain('weekly');
  });

  it('says a daily strategy decides every session, so the wait is the trade not the calendar', () => {
    expect(note('trades', C).sub).toContain('decides every session');
  });

  it('points at the buys, which are the history that does exist', () => {
    expect(note('trades').sub).toContain('Activity');
  });

  it('blames the filter only when a filter really is the reason', () => {
    expect(note('trades', MOM, 'win').title).toBe('No winners yet');
    expect(note('trades', MOM, 'loss').title).toBe('No losers yet');
    // and then it is the filter's doing, so it says so and drops the cadence lecture.
    expect(note('trades', MOM, 'win').sub).toContain('wins');
    expect(note('trades', MOM, 'win').sub).not.toContain('first session');
  });

  it('says nothing specific about a strategy it has no cadence for', () => {
    const unknown = { ...MOM, rulesId: 'something-new' };
    expect(note('trades', unknown).sub).not.toContain('session of each');
    expect(note('trades', unknown).sub).toContain('still open');
  });

  it('a strategy whose paper clock has not started has not traded, not "held"', () => {
    const n = note('trades', { ...MOM, paperStart: null });
    expect(n.title).toBe('Not started');
    expect(n.sub).toContain('has not started');
  });

  it('across all strategies it drops the per-strategy cadence and stays true', () => {
    const n = emptyNote({ what: 'trades', strategy: null, outcome: 'all' });
    expect(n.title).toBe('Nothing sold yet');
    expect(n.sub).toContain('still open');
    expect(n.sub).not.toContain('each month');
  });

  it('an empty activity list is a different sentence from an empty trade list', () => {
    expect(note('activity').title).toBe('Nothing bought yet');
    expect(note('activity').sub).not.toContain('Activity');
  });
});

describe('fillVerb: what one buy or sell actually was', () => {
  it('reads the engine reason, not just the side', () => {
    expect(fillVerb('buy', 'entry')).toBe('Bought');
    expect(fillVerb('buy', 'add')).toBe('Topped up');
    expect(fillVerb('sell', 'trim')).toBe('Trimmed');
    expect(fillVerb('sell', 'signal')).toBe('Sold');
    expect(fillVerb('sell', 'tp')).toBe('Target hit');
    expect(fillVerb('sell', 'sl')).toBe('Stopped out');
    expect(fillVerb('sell', 'time')).toBe('Time exit');
    expect(fillVerb('sell', 'gap')).toBe('Gapped out');
    expect(fillVerb('sell', 'forced')).toBe('Force closed');
  });

  it('falls back to the plain side for a reason it does not know', () => {
    expect(fillVerb('buy', 'nonsense')).toBe('Bought');
    expect(fillVerb('sell', 'nonsense')).toBe('Sold');
  });

  it('covers every reason the engine can write (book_fills_reason_check)', () => {
    // engine/src/seer_engine/sim/book.py FillReason, and migration 003's CHECK constraint.
    for (const r of ['entry', 'add', 'trim', 'signal', 'time', 'gap', 'tp', 'sl', 'forced']) {
      expect(FILL_REASON[r]).toBeDefined();
    }
  });
});

describe('historyHref: one `o` param, two views', () => {
  const trades = { s: 'all', o: 'all', v: 'trades' };
  const act = { s: 'MOM-FR-GT', o: 'buy', v: 'activity' };

  it('omits every default, so the plain page keeps the bare URL', () => {
    expect(historyHref(trades, {})).toBe('/history');
    expect(historyHref(trades, { s: 'all' })).toBe('/history');
  });

  it('keeps what is set', () => {
    expect(historyHref(trades, { s: 'MOM-FR-GT' })).toBe('/history?s=MOM-FR-GT');
    expect(historyHref(trades, { o: 'win' })).toBe('/history?o=win');
    expect(historyHref(act, {})).toBe('/history?s=MOM-FR-GT&o=buy&v=activity');
  });

  it('drops the other view\'s filter on a view change, and keeps the strategy', () => {
    // `o=buy` means nothing in Trades: it would light no button and filter nothing.
    expect(historyHref(act, { v: 'trades' })).toBe('/history?s=MOM-FR-GT');
    expect(historyHref({ s: 'C-GT', o: 'win', v: 'trades' }, { v: 'activity' }))
      .toBe('/history?s=C-GT&v=activity');
  });

  it('keeps the filter when the view does not change', () => {
    expect(historyHref(act, { v: 'activity' })).toBe('/history?s=MOM-FR-GT&o=buy&v=activity');
    expect(historyHref(act, { s: 'C-GT' })).toBe('/history?s=C-GT&o=buy&v=activity');
  });

  it('an explicit filter wins over the view-change reset', () => {
    expect(historyHref(act, { v: 'trades', o: 'loss' })).toBe('/history?s=MOM-FR-GT&o=loss');
  });
});

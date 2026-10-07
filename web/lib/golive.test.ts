import { describe, expect, it } from 'vitest';
import { MAX_DRAWDOWN, MAX_DRAWDOWN_LABEL, MIN_PAPER_MONTHS, MIN_PAPER_MONTHS_LABEL } from './golive';
import { lab } from './sera/lab';

describe('go-live thresholds', () => {
  it('matches the engine constant that the committed lab snapshot carries', () => {
    // `data/lab.json`'s gate is written by `lab.store.snapshot` from `tuning.MAX_DRAWDOWN`.
    // If this fails, the engine moved the bar and `lib/golive.ts` did not follow: the
    // leaderboard would judge every strategy at a threshold the engine no longer uses.
    expect(MAX_DRAWDOWN).toBe(lab.gate.maxDrawdown);
  });

  it('labels the threshold it actually compares against', () => {
    expect(MAX_DRAWDOWN_LABEL).toBe('Max drawdown ≤ 20%');
  });

  // MIN_PAPER_MONTHS has no carrier in the lab snapshot (it is a forward-paper bar, not a lab
  // bar), so this and the engine/web checklist parity test are what keep the two sides together.
  // `backtest.metrics.MIN_PAPER_MONTHS` is the Python twin; move one, move both.
  it('states go-live item 1 as months, counting no trades (design §13)', () => {
    expect(MIN_PAPER_MONTHS).toBe(18);
    expect(MIN_PAPER_MONTHS_LABEL).toBe('≥ 18 months forward');
  });
});

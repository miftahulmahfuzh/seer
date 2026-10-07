import { describe, expect, it } from 'vitest';
import { MAX_DRAWDOWN, MAX_DRAWDOWN_LABEL } from './golive';
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
});

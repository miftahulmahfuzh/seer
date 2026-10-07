/**
 * The go-live thresholds the web judges against (design §1), spelled once.
 *
 * The engine owns these numbers. `MAX_DRAWDOWN` is `backtest.metrics.MAX_DRAWDOWN`, re-exported
 * there as `backtest.tuning.MAX_DRAWDOWN`, and it reaches the web twice over: here, for the
 * leaderboard's six-rule checklist in `lib/metrics.ts`, and in `data/lab.json`'s
 * `gate.maxDrawdown`, written by `lab.store.snapshot`. `golive.test.ts` asserts the two are the
 * same number, so an engine change that is not mirrored here fails the build rather than leaving
 * the leaderboard judging at a bar the engine abandoned.
 *
 * Why not read `data/lab.json` directly: `lib/metrics.ts` is reached from the leaderboard's app
 * code, and importing the lab snapshot outside a server component ships the whole lab to the
 * browser (see the warning at the top of `lib/sera/lab.ts`). Pages that already hold a snapshot
 * must read `gate.maxDrawdown` from it instead of importing this -- `app/sera/how/view.ts` is
 * the model.
 *
 * Raised 0.15 -> 0.2 by the owner on 2026-10-07; design §11 records the revision.
 */
import { pct } from './format';

export const MAX_DRAWDOWN = 0.2;

/** Built from the threshold so the label can never name a number the comparison does not use. */
export const MAX_DRAWDOWN_LABEL = `Max drawdown ≤ ${pct(MAX_DRAWDOWN, 0)}`;

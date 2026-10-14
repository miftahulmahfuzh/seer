/**
 * The go-live thresholds the web judges against (design §1), spelled once.
 *
 * The engine owns these numbers. `MAX_DRAWDOWN` is `backtest.metrics.MAX_DRAWDOWN`, re-exported
 * there as `backtest.tuning.MAX_DRAWDOWN`, and it reaches the web twice over: here, for the
 * leaderboard's five-rule checklist in `lib/metrics.ts`, and in `data/lab.json`'s
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
 * Raised 0.15 -> 0.2 by the owner on 2026-10-07 (design §11) and 0.2 -> 0.25 on 2026-10-14
 * (design §18). This is the REAL-MONEY bar only. On 2026-10-14 the engine split the lab's
 * dev-eligibility screen off it into `backtest.metrics.DEV_MAX_DRAWDOWN` (0.50), which decides
 * what the lab studies rather than what the owner funds. The screen has no mirror here and needs
 * none: the web reads a trial's verdict out of `data/lab.json`'s `failedNow` strings, matching
 * the stable `max DD <= ` prefix in `lib/sera/derive.ts`, never the number.
 */
import { pct } from './format';

export const MAX_DRAWDOWN = 0.25;

/**
 * Go-live condition #1 (design §1, §13): months of forward paper before a real-money decision.
 *
 * The TypeScript twin of `backtest.metrics.MIN_PAPER_MONTHS`, re-exported there as
 * `tuning.MIN_PAPER_MONTHS`. Unlike `MAX_DRAWDOWN` this one has no carrier in `data/lab.json`'s
 * gate -- the lab snapshot describes the LAB's bars, and months of forward paper is not one of
 * them -- so the two sides are kept together by `golive.test.ts` pinning the label and by the
 * engine/web checklist parity test, not by a shared value. Moving it means moving both.
 *
 * Set by the owner on 2026-10-07, replacing "≥ 3 months AND ≥ 100 closed trades": a trade count
 * scales with how many names a book holds, not with how much evidence exists.
 */
export const MIN_PAPER_MONTHS = 18;

/** Built from the threshold so the label can never name a number the comparison does not use. */
export const MIN_PAPER_MONTHS_LABEL = `≥ ${MIN_PAPER_MONTHS} months forward`;

/** Built from the threshold so the label can never name a number the comparison does not use. */
export const MAX_DRAWDOWN_LABEL = `Max drawdown ≤ ${pct(MAX_DRAWDOWN, 0)}`;

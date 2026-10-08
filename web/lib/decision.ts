/**
 * Why there is nothing to act on, in one word, and when the next decision is due.
 *
 * The blank panel (handover Q5): `positions/page.tsx` used to render *nothing* in place of two whole
 * sections whenever the data was stale, and the same blank covered five different situations — the
 * strategy was holding and nothing was due (the common one, roughly three weeks in four), the
 * decision expired at the New York close, nothing was ever produced, the pipeline failed, and paper
 * trading is switched off. Nothing here renders: it only names the state and the times, so both
 * pages say the same words and a test can pin them.
 *
 * Times. The owner reads WIB; every schedule in this repo is UTC. The slots below mirror the three
 * cron lines of `.github/workflows/nightly.yml` and `decision.test.ts` fails if they drift from it:
 * 06:17 UTC = 13:17 WIB, 09:41 = 16:41 WIB, 12:41 = 19:41 WIB.
 */
import { addDays, nextUsSession } from './session';

/**
 * Paper trading is switched off. Mirrors `PAPER_PAUSED` in `.github/workflows/nightly.yml`, which
 * stays the source of truth; `decision.test.ts` reads that file and fails when the two disagree.
 *
 * It is deliberately NOT derived from the database. Measured against the live database on
 * 2026-10-08: the only candidate signature is "the latest run succeeded and its paper step never
 * ran" (`runs.status = 'success' AND runs.paper_status IS NULL`), and it fails twice. It is late —
 * the latest run (id 10, session 2026-10-07) still carries `paper_status = 'success'` from before
 * the pause, so the rule would report "not paused" today. And it is ambiguous — runs 1 and 7 carry
 * exactly that signature for a different reason: paper had not started yet
 * (`strategies.paper_start = 2026-10-07`).
 */
export const PAPER_PAUSED = true;

/**
 * The nightly's cron slots as UTC [hour, minute]: `17 6`, `41 9`, `41 12`. The first is when a
 * decision is due; the last is its final retry, after which silence is a failure rather than a wait.
 */
export const NIGHTLY_SLOTS_UTC: readonly (readonly [number, number])[] = [[6, 17], [9, 41], [12, 41]];

/**
 * The UTC weekdays the nightly runs: cron's `2-6`, Tuesday through Saturday. Cron and
 * `Date.getUTCDay()` use the same numbering (0 = Sunday), so the digits carry over unchanged.
 */
export const NIGHTLY_DAYS_UTC: readonly number[] = [2, 3, 4, 5, 6];

const at = (ymd: string, [h, m]: readonly [number, number]) =>
  new Date(`${ymd}T${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:00Z`);

const utcDay = (ymd: string) => new Date(`${ymd}T12:00:00Z`).getUTCDay();

/**
 * The UTC date of the nightly that owes `session` its decision: the latest Tuesday-to-Saturday on or
 * before it. Tuesday's run reads Monday's session and produces Tuesday's picks; Monday's picks come
 * from Saturday's run, because a session only becomes fetchable at ET midnight (nightly.yml's own
 * comment). Keying the window to this date and not to "the last slot that fired" is what keeps a
 * Monday evening from reading as late: at Monday's close the target is Tuesday, whose run has not
 * come due yet.
 */
export function publishDay(session: string): string {
  let d = session;
  for (let i = 0; i < 7; i++) {
    if (NIGHTLY_DAYS_UTC.includes(utcDay(d))) return d;
    d = addDays(d, -1);
  }
  return session; // unreachable: five days of every seven are in the set
}

/** The session a fresh decision would be for, and the window the nightly has to produce it. */
export type Timing = {
  /** The US session (ET calendar date) new picks target right now. */
  target: string;
  /** The first slot that can produce it: 13:17 WIB on `publishDay(target)`. */
  dueAt: Date;
  /** Its last retry slot, 19:41 WIB. Past this and still nothing is late, not merely pending. */
  lateAfter: Date;
};

export function timing(now: Date): Timing {
  const target = nextUsSession(now);
  const day = publishDay(target);
  return {
    target,
    dueAt: at(day, NIGHTLY_SLOTS_UTC[0]),
    lateAfter: at(day, NIGHTLY_SLOTS_UTC[NIGHTLY_SLOTS_UTC.length - 1]),
  };
}

/**
 * The pipeline, from the page's side:
 * - `never`   no run has ever finished successfully;
 * - `late`    the run that owes `target` a decision has missed its last retry slot;
 * - `waiting` the last good run is spent and the next is not due yet — the routine daily state, and
 *             the one that used to render as a coral alarm;
 * - `current` the last good run targets the session that is coming.
 */
export type PipelineState = 'never' | 'late' | 'waiting' | 'current';

export function pipelineState(
  runSession: string | null, lastGoodRun: Date | null, now: Date,
): PipelineState {
  if (lastGoodRun === null || runSession === null) return 'never';
  const { target, lateAfter } = timing(now);
  if (runSession >= target) return 'current';
  return now.getTime() >= lateAfter.getTime() ? 'late' : 'waiting';
}

/**
 * One strategy's own decision panel:
 * - `never`   paper has not started for it (`paper_state.pending_session` is null);
 * - `live`    it decided, and the decision is for the session that is coming;
 * - `holding` the coming session is not one of its decision sessions — the common state, roughly
 *             three weeks in four for a monthly book. Read from the engine's recorded answer
 *             (`paper_state.pending_decision`, which `decide_book` leaves false on a session that is
 *             neither a rank nor a resize), never re-derived here: those boundaries are NYSE trading
 *             sessions and this module has no trading calendar;
 * - `spent`   whatever it decided was for a session that has closed, OR the strategy has been
 *             retired and superseded. A record, not an order.
 */
export type PanelState = 'never' | 'live' | 'holding' | 'spent';

export function panelState(
  pendingSession: string | null, pendingDecision: boolean, now: Date, retired = false,
): PanelState {
  if (pendingSession === null) return 'never';
  // A retired strategy's last decision is a record whatever its date says. This is the ONE case
  // where a pending row can be dated for a session that has not closed and still must never read
  // as an instruction: an entry is retired and its successor started on the same night, so the
  // predecessor's `pending_session` is the coming session while the predecessor is finished.
  // Measured against production on 2026-10-08: 80 `book_targets` rows and 4 `orders` dated
  // 2026-10-07 carry `pending_decision = true` and belong to entries the roster rebuild retires.
  // They are deliberately NOT deleted -- they are the record of a decision that was made and never
  // acted on -- so the page is the only thing standing between them and the owner's order ticket.
  // That is exactly the failure R5 exists to prevent, and it is handled generically here rather
  // than against any particular rebuild, so it stays true for every future roster change.
  if (retired) return 'spent';
  if (pendingSession < timing(now).target) return 'spent';
  return pendingDecision ? 'live' : 'holding';
}

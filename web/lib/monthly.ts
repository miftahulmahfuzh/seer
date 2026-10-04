// Month-by-month paper performance (D5). Pure: the data layer passes the rows in.
//
// Definitions (the same as metrics.ts):
// - A month's base is the last snapshot before the month; for the first month that is the
//   day-0 snapshot (initial cash, dated the session before paper start).
// - Return = the month's last equity / base equity - 1.
// - SPY = the benchmark's equity on the same two dates, / - 1 (null when either is missing).
// - Trades = closed trades whose exit date falls in the month (the trades metrics.ts counts).
// - Worst drop = the largest peak-to-trough fall within the month, the running peak seeded at
//   the base: (peak - equity) / peak, >= 0.
// - The first month is partial when its base (day 0) is in the same month; the latest month is
//   partial while the next session on the engine's calendar is still in that month.
import { strategyMetrics, type Snapshot } from './metrics';

/** One calendar month of a strategy's paper equity, next to SPY over the same dates. */
export type MonthRow = {
  month: string; // 'YYYY-MM'
  from: string; // base snapshot date
  to: string; // the month's last snapshot date
  return: number;
  spyReturn: number | null;
  trades: number;
  worstDrop: number;
  partial: boolean;
};

/** The whole paper period: day 0 to the latest snapshot. */
export type SinceStartRow = {
  from: string;
  to: string;
  return: number;
  spyReturn: number | null;
  trades: number;
  worstDrop: number;
};

export type MonthlyTable = { months: MonthRow[]; sinceStart: SinceStartRow | null };

export type MonthlyInput = {
  /** The strategy's equity snapshots, day 0 included. Any order. */
  snaps: Snapshot[];
  /** The benchmark's (SPY) snapshots; null when there is no benchmark. */
  spy: Snapshot[] | null;
  /** Exit dates of the strategy's closed trades (closed orders, or non-idle book trades). */
  exitDates: string[];
  /** runStatus().sessionDate: the next session on the engine's calendar; null when unknown. */
  sessionDate: string | null;
};

/** 'YYYY-MM' of a 'YYYY-MM-DD' date. */
export const monthOf = (ymd: string) => ymd.slice(0, 7);

const byDate = (a: Snapshot, b: Snapshot) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0);

function worstDrop(base: number, values: number[]): number {
  let peak = base, worst = 0;
  for (const v of values) {
    peak = Math.max(peak, v);
    worst = Math.max(worst, (peak - v) / peak);
  }
  return worst;
}

/** Month rows oldest first, plus the since-start row. Fewer than two snapshots: nothing to show yet. */
export function monthlyTable({ snaps, spy, exitDates, sessionDate }: MonthlyInput): MonthlyTable {
  const s = [...snaps].sort(byDate);
  if (s.length < 2) return { months: [], sinceStart: null };

  const spyOn = new Map((spy ?? []).map(x => [x.date, x.equity]));
  const spyOver = (from: string, to: string): number | null => {
    const a = spyOn.get(from), b = spyOn.get(to);
    return a === undefined || b === undefined ? null : b / a - 1;
  };
  const tradesIn = new Map<string, number>();
  for (const d of exitDates) tradesIn.set(monthOf(d), (tradesIn.get(monthOf(d)) ?? 0) + 1);

  const day0 = s[0], last = s[s.length - 1];
  const months: MonthRow[] = [];
  let i = 1;
  while (i < s.length) {
    const month = monthOf(s[i].date);
    const base = s[i - 1];
    let j = i;
    while (j < s.length && monthOf(s[j].date) === month) j++;
    const inMonth = s.slice(i, j);
    const end = inMonth[inMonth.length - 1];
    const firstPartial = i === 1 && monthOf(day0.date) === month;
    const latestPartial = j === s.length && (sessionDate === null || monthOf(sessionDate) === month);
    months.push({
      month,
      from: base.date,
      to: end.date,
      return: end.equity / base.equity - 1,
      spyReturn: spyOver(base.date, end.date),
      trades: tradesIn.get(month) ?? 0,
      worstDrop: worstDrop(base.equity, inMonth.map(x => x.equity)),
      partial: firstPartial || latestPartial,
    });
    i = j;
  }

  const all = strategyMetrics(s, []);
  return {
    months,
    sinceStart: {
      from: day0.date,
      to: last.date,
      return: all.totalReturn ?? 0,
      spyReturn: spyOver(day0.date, last.date),
      trades: exitDates.length,
      worstDrop: all.maxDrawdown ?? 0,
    },
  };
}

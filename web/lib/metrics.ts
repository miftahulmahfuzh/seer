import type { Gate } from './strategy';
import { MAX_DRAWDOWN, MAX_DRAWDOWN_LABEL, MIN_PAPER_MONTHS, MIN_PAPER_MONTHS_LABEL } from './golive';

export type Snapshot = { date: string; equity: number };

export type Metrics = {
  totalReturn: number | null;
  winRate: number | null;
  profitFactor: number | null;
  maxDrawdown: number | null;
  trades: number;
  months: number;
};

const DAY = 86_400_000;

/**
 * The curve with the owner's deposits taken out, so it grows only by what the strategy earned
 * (owner, 2026-11-12). Every paper strategy is handed the monthly top-up, and a raw curve counts
 * it as performance: on 2026-10-26 Rp 5,000,000 ($275.30) landed in each book and every card read
 * about +40% on a month in which they all lost money. This is the engine's own rule
 * (`paper/compare.py` `_returns`): a session that received a deposit returns
 * `(equity - deposit) / previous - 1`, and the series is chained from the opening equity, so it
 * keeps that first value and only its ratios mean anything. `deposits` maps a session date to the
 * dollars credited at that session's open (`paper_contributions`, applied rows only). A deposit
 * dated on the first snapshot is part of the opening money, not a step. `snaps` in date order.
 */
export function withoutDeposits(snaps: Snapshot[], deposits: ReadonlyMap<string, number>): Snapshot[] {
  if (deposits.size === 0 || snaps.length < 2) return snaps;
  const out = [snaps[0]];
  for (let i = 1; i < snaps.length; i++) {
    const prev = snaps[i - 1].equity;
    const growth = prev > 0 ? (snaps[i].equity - (deposits.get(snaps[i].date) ?? 0)) / prev : 1;
    out.push({ date: snaps[i].date, equity: out[i - 1].equity * growth });
  }
  return out;
}

/** Metrics over a strategy's equity curve and its closed trades' P/L (USD). */
export function strategyMetrics(snaps: Snapshot[], pnls: number[]): Metrics {
  const wins = pnls.filter(p => p > 0);
  const losses = pnls.filter(p => p <= 0);
  const grossWin = wins.reduce((a, p) => a + p, 0);
  const grossLoss = -losses.reduce((a, p) => a + p, 0);

  let peak = -Infinity, maxDd = 0;
  for (const s of snaps) {
    peak = Math.max(peak, s.equity);
    maxDd = Math.max(maxDd, (peak - s.equity) / peak);
  }

  const first = snaps[0], last = snaps[snaps.length - 1];
  return {
    totalReturn: first ? last.equity / first.equity - 1 : null,
    winRate: pnls.length ? wins.length / pnls.length : null,
    profitFactor: pnls.length ? (grossLoss === 0 ? Infinity : grossWin / grossLoss) : null,
    maxDrawdown: snaps.length ? maxDd : null,
    trades: pnls.length,
    months: first ? (Date.parse(last.date) - Date.parse(first.date)) / DAY / 30.44 : 0,
  };
}

/** One go-live rule: its label, its value and whether it holds. A verdict, never an explanation. */
export type CheckItem = { label: string; val: string; ok: boolean };

/**
 * The fifth rule: "Backtest gate passed", "Not applicable" for C (design §1 item 5), or "Can't be
 * run" for a Claude twin (Seer Adversarial: Claude already knows how the past turned out, so no
 * backtest of a twin is honest). Neither of the last two ever counts as passed. The verdict stands
 * alone: why a gate failed is the method's Sera page to tell, and why a twin's cannot run is the
 * score line's (`leaderboard/view.ts` `scoreOf`).
 */
export function gateItem(gate: Gate): CheckItem {
  if (gate.twin) return { label: 'Backtest gate', val: "Can't be run", ok: false };
  return gate.applicable
    ? { label: 'Backtest gate passed', val: gate.passed ? 'Passed' : 'Not passed', ok: gate.passed }
    : { label: 'Backtest gate', val: 'Not applicable', ok: false };
}

/**
 * The fixed go-live rules from the design doc (§1): four forward-test metrics, then
 * "Backtest gate passed" from `strategies.params.backtest_gate` (D12). All five must hold.
 * The trades item went with design §13 (2026-10-07): a trade count scales with how many
 * names a book holds, not with how much evidence exists, so item 1 is months alone.
 * A strategy whose backtest item is not applicable (C, handover D9) can never pass all five.
 */
export function checklist(m: Metrics, spyReturn: number | null, gate: Gate): CheckItem[] {
  const ret = m.totalReturn ?? 0;
  const p1 = (v: number) => (v >= 0 ? '+' : '−') + Math.abs(v * 100).toFixed(1);
  return [
    {
      label: MIN_PAPER_MONTHS_LABEL,
      val: `${(Math.floor(m.months * 10) / 10).toFixed(1)} mo`,
      ok: m.months >= MIN_PAPER_MONTHS,
    },
    {
      label: 'Beats SPY',
      val: spyReturn === null ? '—' : `${p1(ret)} vs ${p1(spyReturn)}`,
      ok: m.totalReturn !== null && spyReturn !== null && ret > spyReturn,
    },
    {
      label: 'Profit factor ≥ 1.3',
      val: m.profitFactor === null ? '—' : m.profitFactor === Infinity ? '∞' : m.profitFactor.toFixed(2),
      ok: (m.profitFactor ?? 0) >= 1.3,
    },
    {
      label: MAX_DRAWDOWN_LABEL,
      val: m.maxDrawdown === null ? '—' : (m.maxDrawdown * 100).toFixed(1) + '%',
      ok: m.maxDrawdown !== null && m.maxDrawdown <= MAX_DRAWDOWN,
    },
    gateItem(gate),
  ];
}

/**
 * How many rules `checklist` returns. THE definition of that number in `web/`: nothing else may
 * spell it. `metrics.test.ts` asserts `checklist(...)` has exactly this many rows, and
 * `app/(app)/leaderboard/view.ts`'s `CHECKS` is this constant rather than a literal.
 *
 * It is here, beside the list, because a literal elsewhere is exactly how this went wrong: design
 * §13 (2026-10-07, commit `ba8a05b`) folded "≥ 3 months forward AND ≥ 100 trades" into "≥ 18
 * months forward" and shortened this list from six rows to five, while the leaderboard kept its
 * own `CHECKS = 6`. It then scored five rendered rows out of six and `ready` — which requires
 * `items.length === CHECKS` — became unreachable, so a strategy that passed everything read 5/6
 * and never said "Ready for real money".
 *
 * The engine's twin, `backtest.metrics.checklist`, returns FOUR and is not wrong: its missing
 * fifth is the backtest gate, which reads `strategies.params.backtest_gate` — a roster fact no
 * backtest can evaluate — so the web appends `gateItem` and the engine does not. The engine/web
 * parity test compares labels, not lengths, and needs no change when this number moves.
 */
export const CHECKLIST_RULES = 5;

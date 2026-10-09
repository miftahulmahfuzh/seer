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
 * The fifth rule: "Backtest gate passed", or "Not applicable" for C (design §1 item 5), which never
 * counts as passed. The verdict stands alone — why a gate failed is the method's Sera page to tell.
 */
export function gateItem(gate: Gate): CheckItem {
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

import type { Gate } from './strategy';

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

/** One go-live rule. `note` explains a backtest-gate verdict when the roster gives one. */
export type CheckItem = { label: string; val: string; ok: boolean; note?: string };

/**
 * The fixed go-live rules from the design doc (§1): five forward-test metrics, then
 * "Backtest gate passed" from `strategies.params.backtest_gate` (D12). All six must hold.
 */
export function checklist(m: Metrics, spyReturn: number | null, gate: Gate): CheckItem[] {
  const ret = m.totalReturn ?? 0;
  const p1 = (v: number) => (v >= 0 ? '+' : '−') + Math.abs(v * 100).toFixed(1);
  const gateItem: CheckItem = { label: 'Backtest gate passed', val: gate.passed ? 'Passed' : 'Not passed', ok: gate.passed };
  if (gate.note !== null) gateItem.note = gate.note;
  return [
    { label: '≥ 3 months forward', val: `${(Math.floor(m.months * 10) / 10).toFixed(1)} mo`, ok: m.months >= 3 },
    { label: '≥ 100 trades', val: `${m.trades} / 100`, ok: m.trades >= 100 },
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
      label: 'Max drawdown ≤ 15%',
      val: m.maxDrawdown === null ? '—' : (m.maxDrawdown * 100).toFixed(1) + '%',
      ok: m.maxDrawdown !== null && m.maxDrawdown <= 0.15,
    },
    gateItem,
  ];
}

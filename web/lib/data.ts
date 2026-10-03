import { sql } from '@/lib/db';
import { strategyMetrics, type Metrics, type Snapshot } from '@/lib/metrics';
import { isStale } from '@/lib/session';

const n = (v: unknown) => Number(v);
// Date columns are selected as ::text; JS Date parsing would shift them by the server's timezone.
const ymd = (v: unknown) => String(v).slice(0, 10);

export type Strategy = { id: string; name: string; sub: string; icon: string; isChampion: boolean; isBenchmark: boolean };

export async function strategies(): Promise<Strategy[]> {
  const rows = await sql`SELECT id, name, sub, icon, is_champion, is_benchmark FROM strategies ORDER BY sort`;
  return rows.map(r => ({ id: r.id, name: r.name, sub: r.sub, icon: r.icon, isChampion: r.is_champion, isBenchmark: r.is_benchmark }));
}

export async function champion(): Promise<Strategy | null> {
  return (await strategies()).find(s => s.isChampion) ?? null;
}

export type RunStatus = {
  sessionDate: string | null;
  dataDate: string | null;
  finishedAt: Date | null;
  isDemo: boolean;
  stale: boolean;
  usdIdr: number;
};

/** Latest successful pipeline run, whether it's stale, and the IDR rate to display. */
export async function runStatus(now = new Date()): Promise<RunStatus> {
  const [run] = await sql`SELECT session_date::text, data_date::text, finished_at, is_demo FROM runs
    WHERE status = 'success' ORDER BY finished_at DESC LIMIT 1`;
  const [fx] = await sql`SELECT usd_idr FROM fx_rates ORDER BY date DESC LIMIT 1`;
  const sessionDate = run ? ymd(run.session_date) : null;
  return {
    sessionDate,
    dataDate: run ? ymd(run.data_date) : null,
    finishedAt: run ? new Date(run.finished_at) : null,
    isDemo: run?.is_demo ?? false,
    stale: isStale(sessionDate, now),
    usdIdr: fx ? n(fx.usd_idr) : 16500,
  };
}

export type Pick = {
  id: number; slot: number; symbol: string; company: string; last: number;
  limit: number; tp: number; sl: number; shares: number; explanation: string | null;
};

export async function picks(strategyId: string, sessionDate: string): Promise<Pick[]> {
  const rows = await sql`SELECT id, slot, symbol, company, last_price, limit_price, tp_price, sl_price, shares, explanation
    FROM orders WHERE strategy_id = ${strategyId} AND session_date = ${sessionDate} AND status = 'pending' ORDER BY slot`;
  return rows.map(r => ({
    id: n(r.id), slot: r.slot, symbol: r.symbol, company: r.company, last: n(r.last_price),
    limit: n(r.limit_price), tp: n(r.tp_price), sl: n(r.sl_price), shares: r.shares, explanation: r.explanation,
  }));
}

export type Position = {
  id: number; slot: number; symbol: string; company: string; shares: number;
  entry: number; current: number; tp: number; sl: number; day: number; dismissed: boolean;
};

/** Open positions with the latest close as the current price. */
export async function positions(strategyId: string): Promise<Position[]> {
  const rows = await sql`SELECT o.id, o.slot, o.symbol, o.company, o.shares, o.fill_price, o.tp_price, o.sl_price, o.days_held,
      (d.order_id IS NOT NULL) AS dismissed,
      (SELECT b.close FROM bars b WHERE b.symbol = o.symbol ORDER BY b.date DESC LIMIT 1) AS close
    FROM orders o LEFT JOIN action_dismissals d ON d.order_id = o.id
    WHERE o.strategy_id = ${strategyId} AND o.status = 'open' ORDER BY o.days_held DESC, o.slot`;
  return rows.map(r => ({
    id: n(r.id), slot: r.slot, symbol: r.symbol, company: r.company, shares: r.shares,
    entry: n(r.fill_price), current: r.close === null ? n(r.fill_price) : n(r.close),
    tp: n(r.tp_price), sl: n(r.sl_price), day: r.days_held, dismissed: r.dismissed,
  }));
}

export type Trade = {
  id: number; strategyId: string; symbol: string; entry: number; exit: number;
  exitDate: string; reason: 'tp' | 'sl' | 'time' | 'gap'; pnl: number;
};

export async function closedTrades(strategyId: string | null, outcome: 'win' | 'loss' | null): Promise<Trade[]> {
  const rows = await sql`SELECT id, strategy_id, symbol, fill_price, exit_price, exit_date::text, exit_reason, pnl_usd FROM orders
    WHERE status = 'closed'
      AND (${strategyId}::text IS NULL OR strategy_id = ${strategyId})
      AND (${outcome}::text IS NULL OR (${outcome} = 'win') = (pnl_usd > 0))
    ORDER BY exit_date DESC, id DESC LIMIT 300`;
  return rows.map(r => ({
    id: n(r.id), strategyId: r.strategy_id, symbol: r.symbol, entry: n(r.fill_price), exit: n(r.exit_price),
    exitDate: ymd(r.exit_date), reason: r.exit_reason, pnl: n(r.pnl_usd),
  }));
}

export type Board = {
  rows: { strategy: Strategy; metrics: Metrics; curve: Snapshot[] }[];
  from: string | null;
  to: string | null;
};

export async function leaderboard(): Promise<Board> {
  const [strats, snaps, pnls] = await Promise.all([
    strategies(),
    sql`SELECT strategy_id, date::text, equity_usd FROM equity_snapshots ORDER BY date`,
    sql`SELECT strategy_id, pnl_usd FROM orders WHERE status = 'closed'`,
  ]);
  const rows = strats.map(strategy => {
    const curve = snaps.filter(s => s.strategy_id === strategy.id).map(s => ({ date: ymd(s.date), equity: n(s.equity_usd) }));
    const p = pnls.filter(t => t.strategy_id === strategy.id).map(t => n(t.pnl_usd));
    return { strategy, metrics: strategyMetrics(curve, p), curve };
  });
  const dates = snaps.map(s => ymd(s.date));
  return { rows, from: dates[0] ?? null, to: dates[dates.length - 1] ?? null };
}

export async function dismissAction(orderId: number) {
  await sql`INSERT INTO action_dismissals (order_id) VALUES (${orderId}) ON CONFLICT DO NOTHING`;
}

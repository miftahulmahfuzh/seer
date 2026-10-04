import { sql } from '@/lib/db';
import { strategyMetrics, type Metrics, type Snapshot } from '@/lib/metrics';
import { monthlyTable, type MonthlyTable } from '@/lib/monthly';
import { isStale } from '@/lib/session';
import { checksNews, engineOf, parseGate, shortLabel, type Engine, type Gate } from '@/lib/strategy';
import { parseVerdict, type Veto } from '@/lib/vetoes';

export type { Engine, Gate } from '@/lib/strategy';
export type { Veto, Verdict } from '@/lib/vetoes';

type Row = Record<string, any>;

const n = (v: unknown) => Number(v);
const nn = (v: unknown) => (v === null || v === undefined ? null : Number(v));
// Date columns are selected as ::text; JS Date parsing would shift them by the server's timezone.
const ymd = (v: unknown) => String(v).slice(0, 10);
const ymdOrNull = (v: unknown) => (v === null || v === undefined ? null : ymd(v));

/** Design §5: a bracket position is closed by the end of its fifth session. */
export const BRACKET_MAX_DAYS = 5;

export type Strategy = {
  id: string;
  name: string;
  sub: string;
  icon: string;
  isChampion: boolean;
  isBenchmark: boolean;
  /** 'bracket' (A, C), 'book' (F4, F1) or 'benchmark' (SPY). */
  engine: Engine;
  /** 'design-v0', 'monthly-hold'; null for SPY. */
  rulesId: string | null;
  /** First paper session; null until the engine's `paper` command starts the clock. */
  paperStart: string | null;
  /** params->'backtest_gate'; { passed: false, applicable: true, note: null } until `paper` writes the frozen spec. */
  gate: Gate;
  /** A research strategy: its orders and positions are paper only and never a buy recommendation. */
  isPaper: boolean;
  /** 'A', 'C', 'F4', 'F1', 'SPY': the part of the name before the middle dot. */
  short: string;
  /** Runs the nightly news check (C): Positions shows its verdicts under the paper orders. */
  checksNews: boolean;
};

function toStrategy(r: Row): Strategy {
  const isBenchmark = r.is_benchmark === true;
  const isChampion = r.is_champion === true;
  return {
    id: r.id,
    name: r.name,
    sub: r.sub,
    icon: r.icon,
    isChampion,
    isBenchmark,
    engine: engineOf(r.engine, isBenchmark),
    rulesId: r.rules_id ?? null,
    paperStart: ymdOrNull(r.paper_start),
    gate: parseGate(r.gate),
    isPaper: !isBenchmark && !isChampion,
    short: shortLabel(r.name, r.id),
    checksNews: checksNews(r.id, r.spec_object),
  };
}

export async function strategies(): Promise<Strategy[]> {
  const rows = await sql`SELECT id, name, sub, icon, is_champion, is_benchmark, engine, rules_id,
      paper_start::text AS paper_start, params->'backtest_gate' AS gate, params->'spec'->>'object' AS spec_object
    FROM strategies ORDER BY sort, id`;
  return rows.map(toStrategy);
}

export async function champion(): Promise<Strategy | null> {
  return (await strategies()).find(s => s.isChampion) ?? null;
}

export type RunState = 'running' | 'success' | 'failed';
const runState = (v: unknown): RunState | null => (v === 'running' || v === 'success' || v === 'failed' ? v : null);

export type RunStatus = {
  sessionDate: string | null;
  dataDate: string | null;
  finishedAt: Date | null;
  isDemo: boolean;
  stale: boolean;
  usdIdr: number;
  /** Bars step of the most recent run, whatever its outcome; null before the first run. */
  latestStatus: RunState | null;
  /** Paper step of the most recent run; null when it never started (e.g. the bars step failed). */
  paperStatus: RunState | null;
  paperError: string | null;
  paperFinishedAt: Date | null;
};

/**
 * Latest successful pipeline run, whether it's stale, and the IDR rate to display; plus the
 * bars and paper status of the most recent run (successful or not).
 */
export async function runStatus(now = new Date()): Promise<RunStatus> {
  const [[run], [latest], [fx]] = await Promise.all([
    sql`SELECT session_date::text AS session_date, data_date::text AS data_date, finished_at, is_demo FROM runs
      WHERE status = 'success' ORDER BY finished_at DESC LIMIT 1`,
    sql`SELECT status, paper_status, paper_error, paper_finished_at FROM runs ORDER BY started_at DESC, id DESC LIMIT 1`,
    sql`SELECT usd_idr FROM fx_rates ORDER BY date DESC LIMIT 1`,
  ]);
  const sessionDate = run ? ymd(run.session_date) : null;
  return {
    sessionDate,
    dataDate: run ? ymd(run.data_date) : null,
    finishedAt: run ? new Date(run.finished_at) : null,
    isDemo: run?.is_demo ?? false,
    stale: isStale(sessionDate, now),
    usdIdr: fx ? n(fx.usd_idr) : 16500,
    latestStatus: latest ? runState(latest.status) : null,
    paperStatus: latest ? runState(latest.paper_status) : null,
    paperError: latest?.paper_error ?? null,
    paperFinishedAt: latest?.paper_finished_at ? new Date(latest.paper_finished_at) : null,
  };
}

export type Pick = {
  id: number; slot: number; symbol: string; company: string; last: number;
  limit: number; tp: number; sl: number; shares: number; explanation: string | null;
};

/** The champion's pending bracket orders for one session (Today). Unchanged; returns [] for SPY. */
export async function picks(strategyId: string, sessionDate: string): Promise<Pick[]> {
  const rows = await sql`SELECT id, slot, symbol, company, last_price, limit_price, tp_price, sl_price, shares, explanation
    FROM orders WHERE strategy_id = ${strategyId} AND session_date = ${sessionDate} AND status = 'pending' ORDER BY slot`;
  return rows.map(r => ({
    id: n(r.id), slot: r.slot, symbol: r.symbol, company: r.company, last: n(r.last_price),
    limit: n(r.limit_price), tp: n(r.tp_price), sl: n(r.sl_price), shares: r.shares, explanation: r.explanation,
  }));
}

/** One open holding of any engine: a bracket order, a book position, or the SPY benchmark holding. */
export type Holding = {
  /** Unique across engines: 'o:<orders.id>' or 'b:<strategy>:<symbol>'. */
  key: string;
  kind: Engine;
  /** Bracket only: orders.id, for the day-5 "mark as done" action. */
  orderId: number | null;
  /** Bracket only: slot 1..4. */
  slot: number | null;
  symbol: string;
  /** Bracket orders carry a company name; book positions do not. */
  company: string | null;
  /** Whole shares for bracket; book shares are numeric(16,4). */
  shares: number;
  /** Bracket: fill price. Book: the episode's first entry price. */
  entry: number;
  entryDate: string | null;
  /** Mark: orders.mark (else the latest close, else the fill) for bracket; book_positions.mark for book. */
  current: number;
  /** Take profit: always set for bracket; for book only when the rules set one. */
  tp: number | null;
  /** Stop loss: always set for bracket; for book only when the rules set one. */
  sl: number | null;
  /** Sessions held, the fill session counting as 1. */
  day: number;
  /** 5 for bracket (time exit); null for book and benchmark holdings. */
  maxDays: number | null;
  /** shares x current. */
  value: number;
  /** value / the strategy's equity at its last snapshot; null when no equity is known. */
  weight: number | null;
  /** Bracket: (current - entry) x shares. Book: value + income - cost (fees and dividends included). */
  pnl: number;
  /** Bracket: current / entry - 1. Book: (value + income) / cost - 1. */
  pnlPct: number;
  /** Bracket day-5 action marked done. */
  dismissed: boolean;
  /** Book: a sell is decided and executes at the next open. */
  exitPending: boolean;
};

/** A strategy's open holdings: bracket orders (by days held, slot), then book positions (largest first). */
export async function positions(strategyId: string): Promise<Holding[]> {
  const [orders, book] = await Promise.all([
    sql`SELECT o.id, o.slot, o.symbol, o.company, o.shares, o.fill_date::text AS fill_date, o.fill_price,
        o.tp_price, o.sl_price, o.days_held, (d.order_id IS NOT NULL) AS dismissed,
        COALESCE(o.mark, (SELECT b.close FROM bars b WHERE b.symbol = o.symbol ORDER BY b.date DESC LIMIT 1), o.fill_price) AS mark,
        COALESCE((SELECT ps.equity_usd FROM paper_state ps WHERE ps.strategy_id = o.strategy_id),
          (SELECT e.equity_usd FROM equity_snapshots e WHERE e.strategy_id = o.strategy_id ORDER BY e.date DESC LIMIT 1)) AS equity
      FROM orders o LEFT JOIN action_dismissals d ON d.order_id = o.id
      WHERE o.strategy_id = ${strategyId} AND o.status = 'open' ORDER BY o.days_held DESC, o.slot`,
    sql`SELECT p.symbol, p.shares, p.mark, p.entry_date::text AS entry_date, p.entry_price, p.days_held, p.cost_usd, p.income_usd,
        p.stop_price, p.take_price, p.exit_pending, s.engine, s.is_benchmark,
        COALESCE((SELECT ps.equity_usd FROM paper_state ps WHERE ps.strategy_id = p.strategy_id),
          (SELECT e.equity_usd FROM equity_snapshots e WHERE e.strategy_id = p.strategy_id ORDER BY e.date DESC LIMIT 1)) AS equity
      FROM book_positions p JOIN strategies s ON s.id = p.strategy_id
      WHERE p.strategy_id = ${strategyId} ORDER BY p.shares * p.mark DESC, p.symbol`,
  ]);

  const bracket: Holding[] = orders.map(r => {
    const shares = n(r.shares), entry = n(r.fill_price), current = n(r.mark), equity = nn(r.equity);
    const value = shares * current;
    return {
      key: `o:${r.id}`, kind: 'bracket', orderId: n(r.id), slot: n(r.slot), symbol: r.symbol, company: r.company ?? null,
      shares, entry, entryDate: ymdOrNull(r.fill_date), current, tp: n(r.tp_price), sl: n(r.sl_price),
      day: n(r.days_held), maxDays: BRACKET_MAX_DAYS, value, weight: equity ? value / equity : null,
      pnl: (current - entry) * shares, pnlPct: entry > 0 ? current / entry - 1 : 0, dismissed: r.dismissed === true, exitPending: false,
    };
  });

  const held: Holding[] = book.map(r => {
    const engine = engineOf(r.engine, r.is_benchmark === true);
    const shares = n(r.shares), current = n(r.mark), cost = n(r.cost_usd), income = n(r.income_usd), equity = nn(r.equity);
    const value = shares * current;
    return {
      key: `b:${strategyId}:${r.symbol}`, kind: engine === 'benchmark' ? 'benchmark' : 'book', orderId: null, slot: null,
      symbol: r.symbol, company: null, shares, entry: n(r.entry_price), entryDate: ymdOrNull(r.entry_date), current,
      tp: nn(r.take_price), sl: nn(r.stop_price), day: n(r.days_held), maxDays: null, value,
      weight: equity ? value / equity : null, pnl: value + income - cost, pnlPct: cost > 0 ? (value + income) / cost - 1 : 0,
      dismissed: false, exitPending: r.exit_pending === true,
    };
  });

  return [...bracket, ...held];
}

/** One order or target a strategy has decided for its next session. */
export type PendingOrder = {
  /** 'o:<orders.id>' or 't:<strategy>:<session>:<symbol>'. */
  key: string;
  kind: 'bracket' | 'book';
  sessionDate: string;
  /** Bracket: the slot. Book: the target's rank (1 = best). */
  rank: number;
  slot: number | null;
  symbol: string;
  company: string | null;
  last: number;
  limit: number | null;
  tp: number | null;
  sl: number | null;
  /** Bracket: sized whole shares. Book: null (sized from the weight at the open). */
  shares: number | null;
  /** Book: target weight of equity, (0, 1]. Bracket: null. */
  weight: number | null;
  explanation: string | null;
};

export type Pending = {
  /** The session these are for: paper_state.pending_session, else the bracket orders' own session. */
  sessionDate: string | null;
  /** False when a book strategy's next session is not a decision session (it changes nothing), and for SPY. */
  decision: boolean;
  orders: PendingOrder[];
};

/** What a strategy will do at the next session: pending bracket orders, or a book decision's targets. */
export async function pendingOrders(strategyId: string): Promise<Pending> {
  const [[st], [ps], orders, targets] = await Promise.all([
    sql`SELECT engine, is_benchmark FROM strategies WHERE id = ${strategyId}`,
    sql`SELECT pending_session::text AS pending_session, pending_decision FROM paper_state WHERE strategy_id = ${strategyId}`,
    sql`SELECT id, session_date::text AS session_date, slot, symbol, company, last_price, limit_price, tp_price, sl_price,
        shares, explanation
      FROM orders WHERE strategy_id = ${strategyId} AND status = 'pending' ORDER BY session_date, slot`,
    sql`SELECT t.session_date::text AS session_date, t.rank, t.symbol, t.weight, t.last_price, t.limit_price,
        t.stop_price, t.take_price, t.explanation
      FROM paper_state ps JOIN book_targets t ON t.strategy_id = ps.strategy_id AND t.session_date = ps.pending_session
      WHERE ps.strategy_id = ${strategyId} AND ps.pending_decision ORDER BY t.rank`,
  ]);
  if (!st) return { sessionDate: null, decision: false, orders: [] };
  const engine = engineOf(st.engine, st.is_benchmark === true);
  const pendingSession = ps ? ymdOrNull(ps.pending_session) : null;

  if (engine === 'bracket') {
    const items: PendingOrder[] = orders.map(r => ({
      key: `o:${r.id}`, kind: 'bracket', sessionDate: ymd(r.session_date), rank: n(r.slot), slot: n(r.slot),
      symbol: r.symbol, company: r.company ?? null, last: n(r.last_price), limit: n(r.limit_price),
      tp: n(r.tp_price), sl: n(r.sl_price), shares: n(r.shares), weight: null, explanation: r.explanation ?? null,
    }));
    return { sessionDate: pendingSession ?? items[0]?.sessionDate ?? null, decision: true, orders: items };
  }
  if (engine === 'book') {
    const items: PendingOrder[] = targets.map(r => ({
      key: `t:${strategyId}:${ymd(r.session_date)}:${r.symbol}`, kind: 'book', sessionDate: ymd(r.session_date),
      rank: n(r.rank), slot: null, symbol: r.symbol, company: null, last: n(r.last_price), limit: nn(r.limit_price),
      tp: nn(r.take_price), sl: nn(r.stop_price), shares: null, weight: n(r.weight), explanation: r.explanation ?? null,
    }));
    return { sessionDate: pendingSession, decision: ps?.pending_decision === true, orders: items };
  }
  return { sessionDate: pendingSession, decision: false, orders: [] };
}

/**
 * The news check's verdicts for one strategy and session (`news_vetoes`, migration 004), every
 * verdict, by rank in A's list. Empty when the `veto` step did not run (or found no candidates).
 */
export async function vetoes(strategyId: string, sessionDate: string): Promise<Veto[]> {
  const rows = await sql`SELECT rank, symbol, verdict, reason, jsonb_array_length(headlines) AS headline_count,
      earnings_date::text AS earnings_date, decided_at
    FROM news_vetoes WHERE strategy_id = ${strategyId} AND session_date = ${sessionDate} ORDER BY rank`;
  return rows.map(r => ({
    rank: n(r.rank), symbol: r.symbol, verdict: parseVerdict(r.verdict), reason: String(r.reason ?? ''),
    headlineCount: n(r.headline_count), earningsDate: ymdOrNull(r.earnings_date),
    decidedAt: new Date(r.decided_at).toISOString(),
  }));
}

/** Bracket exits (design §5) plus the book engine's signal and forced exits. */
export type ExitReason = 'tp' | 'sl' | 'time' | 'gap' | 'signal' | 'forced';

export type Trade = {
  /** Unique across engines: 'o:<orders.id>' or 'b:<book_trades.id>'. */
  key: string;
  /** Row id within its own table (orders or book_trades): not unique across engines. */
  id: number;
  kind: 'bracket' | 'book';
  strategyId: string;
  /** 'A', 'F4', 'F1': the strategy's short label. */
  strategyShort: string;
  symbol: string;
  entry: number;
  exit: number;
  entryDate: string | null;
  exitDate: string;
  /** Bracket: whole shares. Book: null (book_trades keeps no share count). */
  shares: number | null;
  days: number | null;
  reason: ExitReason;
  pnl: number;
};

/** Closed trades of every engine (closed orders and non-idle book trades), newest first, at most 300. */
export async function closedTrades(strategyId: string | null, outcome: 'win' | 'loss' | null): Promise<Trade[]> {
  const rows = await sql`SELECT x.kind, x.id, x.strategy_id, s.name, s.id AS sid, x.symbol, x.entry_price, x.exit_price,
      x.entry_date::text AS entry_date, x.exit_date::text AS exit_date, x.shares, x.days_held, x.exit_reason, x.pnl_usd
    FROM (
      SELECT 'bracket' AS kind, o.id, o.strategy_id, o.symbol, o.fill_price AS entry_price, o.exit_price,
        o.fill_date AS entry_date, o.exit_date, o.shares::numeric AS shares, o.days_held, o.exit_reason, o.pnl_usd
      FROM orders o WHERE o.status = 'closed'
      UNION ALL
      SELECT 'book' AS kind, t.id, t.strategy_id, t.symbol, t.entry_price, t.exit_price,
        t.entry_date, t.exit_date, NULL::numeric AS shares, t.days_held, t.exit_reason, t.pnl_usd
      FROM book_trades t WHERE NOT t.idle
    ) x JOIN strategies s ON s.id = x.strategy_id
    WHERE (${strategyId}::text IS NULL OR x.strategy_id = ${strategyId})
      AND (${outcome}::text IS NULL OR (${outcome} = 'win') = (x.pnl_usd > 0))
    ORDER BY x.exit_date DESC, x.kind, x.id DESC LIMIT 300`;
  return rows.map(r => ({
    key: `${r.kind === 'book' ? 'b' : 'o'}:${r.id}`, id: n(r.id), kind: r.kind === 'book' ? 'book' : 'bracket',
    strategyId: r.strategy_id, strategyShort: shortLabel(r.name, r.sid), symbol: r.symbol,
    entry: n(r.entry_price), exit: n(r.exit_price), entryDate: ymdOrNull(r.entry_date), exitDate: ymd(r.exit_date),
    shares: nn(r.shares), days: nn(r.days_held), reason: r.exit_reason as ExitReason, pnl: n(r.pnl_usd),
  }));
}

/** Which closed-trade rows count for a strategy: closed orders (bracket), non-idle book trades (book), none (benchmark). */
const countsFor = (engine: Engine, src: unknown) => engine !== 'benchmark' && src === engine;

export type Board = {
  rows: { strategy: Strategy; metrics: Metrics; curve: Snapshot[] }[];
  from: string | null;
  to: string | null;
};

/** Every strategy's metrics over all its snapshots (day 0 included) and its own engine's closed trades. */
export async function leaderboard(): Promise<Board> {
  const [strats, snaps, pnls] = await Promise.all([
    strategies(),
    sql`SELECT strategy_id, date::text AS date, equity_usd FROM equity_snapshots ORDER BY date`,
    sql`SELECT 'bracket' AS src, strategy_id, pnl_usd FROM orders WHERE status = 'closed'
      UNION ALL SELECT 'book' AS src, strategy_id, pnl_usd FROM book_trades WHERE NOT idle`,
  ]);
  const rows = strats.map(strategy => {
    const curve = snaps.filter(s => s.strategy_id === strategy.id).map(s => ({ date: ymd(s.date), equity: n(s.equity_usd) }));
    const p = pnls.filter(t => t.strategy_id === strategy.id && countsFor(strategy.engine, t.src)).map(t => n(t.pnl_usd));
    return { strategy, metrics: strategyMetrics(curve, p), curve };
  });
  const dates = snaps.map(s => ymd(s.date));
  return { rows, from: dates[0] ?? null, to: dates[dates.length - 1] ?? null };
}

/**
 * Month-by-month paper performance of one strategy next to the benchmark (D5), for the
 * Leaderboard's monthly sheet. `sessionDate` is runStatus().sessionDate (marks the current month partial).
 */
export async function monthly(strategyId: string, sessionDate: string | null): Promise<MonthlyTable> {
  const strats = await strategies();
  const st = strats.find(x => x.id === strategyId);
  if (!st) return { months: [], sinceStart: null };
  const bench = strats.find(x => x.isBenchmark) ?? null;
  const none = Promise.resolve([] as Row[]);
  const [snaps, spy, exits] = await Promise.all([
    sql`SELECT date::text AS date, equity_usd FROM equity_snapshots WHERE strategy_id = ${st.id} ORDER BY date`,
    bench ? sql`SELECT date::text AS date, equity_usd FROM equity_snapshots WHERE strategy_id = ${bench.id} ORDER BY date` : none,
    st.engine === 'bracket'
      ? sql`SELECT exit_date::text AS exit_date FROM orders WHERE strategy_id = ${st.id} AND status = 'closed'`
      : st.engine === 'book'
        ? sql`SELECT exit_date::text AS exit_date FROM book_trades WHERE strategy_id = ${st.id} AND NOT idle`
        : none,
  ]);
  const toSnap = (r: Row): Snapshot => ({ date: ymd(r.date), equity: n(r.equity_usd) });
  return monthlyTable({
    snaps: snaps.map(toSnap),
    spy: bench ? spy.map(toSnap) : null,
    exitDates: exits.map(r => ymd(r.exit_date)),
    sessionDate,
  });
}

export async function dismissAction(orderId: number) {
  await sql`INSERT INTO action_dismissals (order_id) VALUES (${orderId}) ON CONFLICT DO NOTHING`;
}

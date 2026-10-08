/**
 * The Plan's reads (Sean phase 5): the followed roster method, its newest picks, the owner's done
 * marks, the latest closes, and the reminders built from them. Server only (opens Neon through
 * lib/db); never unit-tested (plan invariant 7) -- the logic lives in the pure reminders.ts.
 */
import { cache } from 'react';
import { sql } from '@/lib/db';
import { cashUsd, OWNER_MONTHLY, OWNER_USD_IDR } from '@/lib/sean/cash';
import { ledgerOrders } from '@/lib/sean/data';
import { orderSession } from '@/lib/sean/ledger';
import {
  buildReminders, outsideShares, planOrders, resizes, sharesBySymbol,
  type ReminderMark, type ReminderPlan, type Side, type Target,
} from '@/lib/sean/reminders';
import { shortLabel } from '@/lib/strategy';

/** A roster method Sean can follow: active, book engine (it holds a basket), not the benchmark. */
export type LinkableMethod = {
  id: string;
  /** 'RAW': the part of the name before the middle dot. */
  short: string;
  /** 'RAW · Unbraked momentum'. */
  name: string;
  sub: string;
  /** strategies.icon (a Lucide name; components/roster.ts strategyIcon). */
  icon: string;
  rulesId: string | null;
  /** Its newest decision's session (book_targets), YYYY-MM-DD; null before its first pick. */
  lastPick: string | null;
};

export async function linkableMethods(): Promise<LinkableMethod[]> {
  const rows = await sql`SELECT s.id, s.name, s.sub, s.icon, s.rules_id,
      (SELECT max(t.session_date)::text FROM book_targets t WHERE t.strategy_id = s.id) AS last_pick
    FROM strategies s
    WHERE s.status = 'active' AND s.engine = 'book' AND NOT s.is_benchmark
    ORDER BY s.sort, s.id`;
  return rows.map(r => ({
    id: r.id,
    short: shortLabel(r.name, r.id),
    name: r.name,
    sub: r.sub ?? '',
    icon: r.icon ?? '',
    rulesId: r.rules_id ?? null,
    lastPick: r.last_pick ? String(r.last_pick).slice(0, 10) : null,
  }));
}

/** The followed method (sean_link, singleton) joined to its roster row. */
export type SeanLink = {
  strategyId: string;
  /** Orders whose New York trade date is on or after this belong to the plan. */
  since: string;
  /** The owner's plan size; null = what the plan holds now. */
  budgetUsd: number | null;
  /** The opening deposit in dollars, read off the broker balance; null = convert initialIdr. */
  openingUsd: number | null;
  short: string;
  name: string;
  sub: string;
  icon: string;
  rulesId: string | null;
  /** The method left the roster: no picks to follow. */
  retired: boolean;
};

export async function link(): Promise<SeanLink | null> {
  const [r] = await sql`SELECT l.strategy_id, l.since::text AS since, l.budget_usd, l.opening_usd,
      s.name, s.sub, s.icon, s.rules_id, s.status
    FROM sean_link l JOIN strategies s ON s.id = l.strategy_id
    WHERE l.id = 1`;
  if (!r) return null;
  return {
    strategyId: r.strategy_id,
    since: String(r.since).slice(0, 10),
    budgetUsd: r.budget_usd === null || r.budget_usd === undefined ? null : Number(r.budget_usd),
    openingUsd: r.opening_usd === null || r.opening_usd === undefined ? null : Number(r.opening_usd),
    short: shortLabel(r.name, r.strategy_id),
    name: r.name,
    sub: r.sub ?? '',
    icon: r.icon ?? '',
    rulesId: r.rules_id ?? null,
    retired: r.status === 'retired',
  };
}

/** A method's newest decision. `pending`: its paper book has not traded that session yet. */
export type LatestTargets = { sessionDate: string; pending: boolean; targets: Target[] };

export async function latestTargets(strategyId: string): Promise<LatestTargets | null> {
  const rows = await sql`SELECT t.session_date::text AS session_date, t.symbol, t.weight, t.last_price,
      COALESCE(ps.pending_decision AND ps.pending_session = t.session_date, false) AS pending
    FROM book_targets t
    LEFT JOIN paper_state ps ON ps.strategy_id = t.strategy_id
    WHERE t.strategy_id = ${strategyId}
      AND t.session_date = (SELECT max(session_date) FROM book_targets WHERE strategy_id = ${strategyId})
    ORDER BY t.rank`;
  if (rows.length === 0) return null;
  return {
    sessionDate: String(rows[0].session_date).slice(0, 10),
    pending: rows[0].pending === true,
    targets: rows.map(r => ({ symbol: r.symbol, weight: Number(r.weight), last: Number(r.last_price) })),
  };
}

/** The owner's done marks for one decision of one method. */
export async function reminderMarks(strategyId: string, sessionDate: string): Promise<ReminderMark[]> {
  const rows = await sql`SELECT session_date::text AS session_date, symbol, action
    FROM sean_reminder_marks
    WHERE strategy_id = ${strategyId} AND session_date = ${sessionDate}::date`;
  return rows.map(r => ({
    sessionDate: String(r.session_date).slice(0, 10),
    symbol: r.symbol,
    side: (r.action === 'sell' ? 'sell' : 'buy') as Side,
  }));
}

/**
 * The newest daily close per stock in sean_marks (written nightly by the engine, phase 4).
 * Named apart from phase 3's marks() on purpose. Stocks without a close are absent.
 */
export async function latestCloses(symbols: string[]): Promise<Map<string, number>> {
  const out = new Map<string, number>();
  if (symbols.length === 0) return out;
  const rows = await sql`SELECT DISTINCT ON (symbol) symbol, close
    FROM sean_marks WHERE symbol = ANY(${symbols}::text[])
    ORDER BY symbol, date DESC`;
  for (const r of rows) out.set(r.symbol, Number(r.close));
  return out;
}

/**
 * The newest USD/IDR rate the engine has stored (fx_rates, written by the data workflows), used to
 * put the owner's rupiah contributions into dollars. Falls back to OWNER_USD_IDR -- the rate his
 * real 10,000,000 IDR was converted at -- when the table is empty, so a missing row costs accuracy
 * and never the page.
 */
export async function latestUsdIdr(): Promise<number> {
  const [r] = await sql`SELECT usd_idr FROM fx_rates ORDER BY date DESC LIMIT 1`;
  const rate = r === undefined ? NaN : Number(r.usd_idr);
  return Number.isFinite(rate) && rate > 0 ? rate : OWNER_USD_IDR;
}

/** Everything /sean/plan shows once a method is followed. */
export type PlanState = {
  link: SeanLink;
  /** The method's newest decision; null before its first pick or once it is retired. */
  targets: LatestTargets | null;
  plan: ReminderPlan;
  /** Stocks held from outside the plan (before `since`), by ticker: never sold by Sean. */
  outside: string[];
};

/** The followed method, its picks and the reminders against the plan; null when nothing is followed. */
export async function planState(): Promise<PlanState | null> {
  const l = await link();
  if (!l) return null;
  const [decision, all] = await Promise.all([
    l.retired ? Promise.resolve(null) : latestTargets(l.strategyId),
    ledgerOrders(),
  ]);
  const inPlan = planOrders(all, l.since);
  const held = sharesBySymbol(inPlan);
  const outside = outsideShares(sharesBySymbol(all), held);
  const [marksDone, closes, usdIdr] = await Promise.all([
    decision ? reminderMarks(l.strategyId, decision.sessionDate) : Promise.resolve([] as ReminderMark[]),
    latestCloses([...held.keys()]),
    latestUsdIdr(),
  ]);
  // The wallet, derived: the contribution schedule from the plan's own start date, less what the
  // plan's orders have spent. `through` is today's New York date -- the same calendar plan
  // membership is counted in (planOrders / orderSession), so the deposits and the orders are
  // sliced consistently.
  const cash = cashUsd({
    schedule: { ...OWNER_MONTHLY, startDate: l.since, openingUsd: l.openingUsd },
    through: orderSession(new Date().toISOString()),
    usdIdr,
    orders: inPlan.map(o => ({ side: o.side, totalUsd: o.totalUsd })),
  });
  const plan = buildReminders({
    sessionDate: decision?.sessionDate ?? l.since,
    targets: decision?.targets ?? [],
    resizes: resizes(l.rulesId),
    held,
    outside,
    closes,
    budgetUsd: l.budgetUsd,
    cashUsd: cash,
    orders: inPlan.map(o => ({ symbol: o.symbol, side: o.side, executedAt: o.executedAt, price: o.price })),
    marks: marksDone,
  });
  return { link: l, targets: decision, plan, outside: [...outside.keys()].sort() };
}

/**
 * Open reminders, for the Plan tab badge and the coral dot on Seer's Sean buttons (rail and phone
 * header). 0 when nothing is followed and when anything fails: a badge must never take a page
 * down. React `cache`: (app)/layout.tsx and AppHeader both ask during one request, and planState
 * runs once.
 */
export const openReminderCount = cache(async (): Promise<number> => {
  try {
    const st = await planState();
    return st ? st.plan.open.length : 0;
  } catch {
    return 0;
  }
});

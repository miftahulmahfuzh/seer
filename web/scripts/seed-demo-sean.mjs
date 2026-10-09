// Fills Sean's tables with demo data, so /sean, /sean/trades and /sean/plan show a real-looking
// story instead of three empty states. Run it after `npm run db:seed-demo`, against the same demo
// database -- it reads that seeder's roster and book targets and buys them.
//
// The story it tells, which is the one Sean was built for:
//   * PLTR bought long before the plan started -- a personal holding Sean must never sell;
//   * the plan begins on F4's first decision: the owner buys all 13 of its picks;
//   * F4 rotates on its next decision: four names leave, nine of twelve new ones are bought, and
//     three are left unbought so the Plan page has live buy reminders to show;
//   * a sell of PLTR funds the rotation, and the NVDA bought with the proceeds two minutes later
//     is claimed as the owner's own (`sean_own_orders`, migration 020), so its shares stay out of
//     the plan.
//
// Fees are Gotrade's real schedule (engine/src/seer_engine/sim/costs.py, measured from the owner's
// own receipts), priced at the regime in force on each order's date -- so the demo's totals are
// arithmetic the Trades page can check, not invented numbers.
//
// The ledger math mirrors lib/sean/ledger.ts (contract B): average cost per symbol, fees inside
// the cost, a sell realising proceeds minus shares x average.
//
// Refuses to run unless the roster is the demo one, so it can never touch the real database.
// `--dry-run` builds every row and prints the counts without writing.
import { Pool, neonConfig } from '@neondatabase/serverless';
import ws from 'ws';

const DRY_RUN = process.argv.includes('--dry-run');

// --- money, in integer cents -------------------------------------------------
const HALF_UP = v => Math.floor(v + 0.5);
const HALF_DOWN = v => Math.ceil(v - 0.5);
const CEIL = v => Math.ceil(v - 1e-9);
const usd = c => +(c / 100).toFixed(2);

// Gotrade's fee regimes, oldest first (engine sim/costs.py GOTRADE). Rates are fractions of the
// order amount; `tradingMin`, `regulatoryCap` are cents.
const REGIMES = [
  { since: '2025-06-10', trading: 0, tradingMin: 0, regulatory: 0.003, regulatoryCap: null, sellExtra: 0, ppn: 0 },
  { since: '2025-06-26', trading: 0.003, tradingMin: 10, regulatory: 0.00054, regulatoryCap: 10, sellExtra: 0.0004, ppn: 0.11 },
  { since: '2026-03-25', trading: 0.003, tradingMin: 10, regulatory: 0.00054, regulatoryCap: 11, sellExtra: 0.0004, ppn: 0.11 },
  { since: '2026-06-16', trading: 0.002, tradingMin: 10, regulatory: 0.00054, regulatoryCap: 11, sellExtra: 0.0004, ppn: 0.11 },
];

const regimeOn = date => {
  let found = null;
  for (const r of REGIMES) if (r.since <= date) found = r;
  if (!found) throw new Error(`no Gotrade fee regime on ${date}`);
  return found;
};

/** One order's fees, in cents, exactly as a receipt prints them. */
function fees(side, amountCents, date) {
  const r = regimeOn(date);
  const a = Math.max(amountCents, 1);
  const trading = Math.max(HALF_UP(r.trading * a), r.tradingMin);
  let regulatory = CEIL(r.regulatory * a);
  if (r.regulatoryCap !== null) regulatory = Math.min(regulatory, r.regulatoryCap);
  if (side === 'sell') regulatory += CEIL(r.sellExtra * a);
  const ppn = HALF_DOWN(r.ppn * (trading + regulatory));
  return { trading, regulatory, ppn, total: trading + regulatory + ppn };
}

// --- dates -------------------------------------------------------------------
const addDays = (ymd, n) => { const d = new Date(`${ymd}T12:00:00Z`); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
const weekend = ymd => [0, 6].includes(new Date(`${ymd}T12:00:00Z`).getUTCDay());
const sessionsBetween = (from, to) => { const out = []; for (let d = from; d <= to; d = addDays(d, 1)) if (!weekend(d)) out.push(d); return out; };
/** A New York fill at 15:4x, written as the WIB timestamp a Gotrade receipt prints (+07:00, next day). */
const wib = (session, minute) => `${addDays(session, 1)}T0${2 + Math.floor(minute / 60)}:${String(minute % 60).padStart(2, '0')}:00+07:00`;

// --- deterministic randomness ------------------------------------------------
let seed = 20261009;
const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;

// --- read the demo roster ----------------------------------------------------
neonConfig.webSocketConstructor = ws;
const pool = new Pool({ connectionString: process.env.DATABASE_URL_UNPOOLED });
const c = await pool.connect();
let counts;
try {
  const demo = await c.query(`SELECT count(*)::int AS n FROM strategies WHERE params->>'demo' = 'true'`);
  const real = await c.query(`SELECT count(*)::int AS n FROM strategies WHERE coalesce(params->>'demo', 'false') <> 'true'`);
  if (demo.rows[0].n === 0 || real.rows[0].n > 0) {
    throw new Error('this is not a demo database (run scripts/seed-demo.mjs first); refusing to write Sean demo rows.');
  }

  const [{ data_date: dataDate }] = (await c.query('SELECT max(data_date)::text AS data_date FROM runs')).rows;
  const [{ strategy_id: METHOD }] = (await c.query(
    `SELECT strategy_id FROM book_targets GROUP BY strategy_id ORDER BY count(*) DESC LIMIT 1`)).rows;
  const targetRows = (await c.query(
    `SELECT session_date::text AS session, rank, symbol, weight::float8 AS weight, last_price::float8 AS last
       FROM book_targets WHERE strategy_id = $1 ORDER BY session_date, rank`, [METHOD])).rows;
  const marks = Object.fromEntries((await c.query(
    `SELECT symbol, mark::float8 AS mark FROM book_positions WHERE strategy_id = $1`, [METHOD])).rows
    .map(r => [r.symbol, r.mark]));

  const decisions = [...new Set(targetRows.map(r => r.session))].sort();
  if (decisions.length < 2) throw new Error('the demo method needs two decisions to rotate between');
  const FIRST = decisions[0];
  const LAST_DECISION = decisions[decisions.length - 1];
  const picksOf = s => targetRows.filter(r => r.session === s);

  // --- the price of every symbol on every session ----------------------------
  const sessions = sessionsBetween(FIRST, dataDate);
  const symbols = [...new Set([...targetRows.map(r => r.symbol), 'PLTR', 'NVDA'])].sort();
  const ANCHOR = { PLTR: 61.4, NVDA: 186.95 };
  const priceOf = {}; // symbol -> { session: close }
  for (const sym of symbols) {
    const last = marks[sym] ?? ANCHOR[sym] ?? targetRows.filter(r => r.symbol === sym).at(-1).last;
    const path = [last];
    for (let i = sessions.length - 2; i >= 0; i--) path.unshift(+(path[0] / (1 + (rnd() - 0.48) * 0.022)).toFixed(4));
    priceOf[sym] = Object.fromEntries(sessions.map((s, i) => [s, path[i]]));
  }
  const priceAt = (sym, session) => priceOf[sym][session] ?? priceOf[sym][sessions[0]];

  // --- orders ----------------------------------------------------------------
  const orders = []; // { side, orderType, symbol, session, minute, price, shares }
  const buy = (symbol, session, minute, price, shares) =>
    orders.push({ side: 'buy', orderType: 'Market Buy', symbol, session, minute, price, shares });
  const sell = (symbol, session, minute, price, shares) =>
    orders.push({ side: 'sell', orderType: 'Market Sell', symbol, session, minute, price, shares });

  // The personal holding, bought long before the plan: Sean must never sell it.
  buy('PLTR', '2025-06-10', 12, 24.18, 4.136476);

  // Day one of the plan: every pick of the first decision, sized by weight.
  const FIRST_CASH = 1400;
  const first = picksOf(FIRST);
  first.forEach((t, i) => {
    const px = priceAt(t.symbol, FIRST);
    buy(t.symbol, FIRST, 30 + i, px, +((FIRST_CASH * t.weight) / px).toFixed(6));
  });

  // The rotation: four names leave, nine of twelve new ones are bought.
  const held = new Set(first.map(t => t.symbol));
  const next = picksOf(LAST_DECISION);
  const wanted = new Set(next.map(t => t.symbol));
  const leaving = [...held].filter(s => !wanted.has(s));
  const bought = first.map(t => [t.symbol, +((FIRST_CASH * t.weight) / priceAt(t.symbol, FIRST)).toFixed(6)]);
  const sharesOf = Object.fromEntries(bought);
  leaving.forEach((sym, i) => sell(sym, LAST_DECISION, 20 + i, priceAt(sym, LAST_DECISION), sharesOf[sym]));

  // The owner's own rotation, two minutes apart: PLTR out, NVDA in. Neither belongs to the plan,
  // and the NVDA buy is claimed as his own (migration 020) so its shares stay outside it.
  const SWAP = sessions.at(-2);
  const pltrPx = priceAt('PLTR', SWAP);
  sell('PLTR', SWAP, 51, pltrPx, 4.136476);
  const OWN_NVDA = orders.length; // the index of the buy about to be pushed
  buy('NVDA', SWAP, 53, priceAt('NVDA', SWAP), 0.425);

  const SKIPPED = 3; // left unbought on purpose: the Plan page needs live buy reminders
  const ROTATION_CASH = 1400;
  const incoming = next.filter(t => !held.has(t.symbol)).slice(0, -SKIPPED);
  incoming.forEach((t, i) => {
    const px = priceAt(t.symbol, LAST_DECISION);
    buy(t.symbol, LAST_DECISION, 34 + i, px, +((ROTATION_CASH * t.weight) / px).toFixed(6));
  });

  // --- the receipt each order would print ------------------------------------
  const receipts = orders
    .map((o, i) => {
      const amount = HALF_UP(o.price * o.shares * 100);
      const f = fees(o.side, amount, o.session);
      const total = o.side === 'buy' ? amount + f.total : amount - f.total;
      return {
        ...o,
        i,
        executedAt: wib(o.session, o.minute),
        amountUsd: usd(amount),
        tradingFeeUsd: usd(f.trading),
        regulatoryFeeUsd: usd(f.regulatory),
        ppnUsd: usd(f.ppn),
        totalUsd: usd(total),
        // Gotrade's own "Net Profit" on a sell: proceeds against the purchase amount, no buy fees.
        netProfitUsd: o.side === 'sell' ? usd(total - HALF_UP(priceAt(o.symbol, FIRST) * o.shares * 100)) : null,
      };
    })
    .sort((a, b) => (a.executedAt < b.executedAt ? -1 : a.executedAt > b.executedAt ? 1 : a.i - b.i));

  // --- the nightly P&L series (lib/sean/ledger.ts, contract B) ---------------
  const book = new Map(); // symbol -> { shares, cost }
  let realized = 0;
  let feesPaid = 0;
  let cursor = 0;
  const equity = [];
  for (const date of sessions) {
    while (cursor < receipts.length && receipts[cursor].session <= date) {
      const o = receipts[cursor++];
      feesPaid += o.tradingFeeUsd + o.regulatoryFeeUsd + o.ppnUsd;
      const p = book.get(o.symbol) ?? { shares: 0, cost: 0 };
      if (o.side === 'buy') {
        p.shares += o.shares;
        p.cost += o.totalUsd;
      } else {
        const s = Math.min(o.shares, p.shares);
        if (s > 0) {
          const avg = p.cost / p.shares;
          const proceeds = s === o.shares ? o.totalUsd : (o.totalUsd * s) / o.shares;
          realized += proceeds - s * avg;
          p.cost -= s * avg;
          p.shares -= s;
        }
      }
      if (p.shares < 1e-9) { p.shares = 0; p.cost = 0; }
      book.set(o.symbol, p);
    }
    let value = 0;
    let cost = 0;
    for (const [sym, p] of book) {
      if (p.shares === 0) continue;
      value += p.shares * priceAt(sym, date);
      cost += p.cost;
    }
    equity.push({ date, value: usd(Math.round(value * 100)), cost: usd(Math.round(cost * 100)),
      realized: usd(Math.round(realized * 100)), unrealized: usd(Math.round((value - cost) * 100)),
      pnl: usd(Math.round((realized + value - cost) * 100)), fees: usd(Math.round(feesPaid * 100)) });
  }

  // Closes for every symbol the owner has held, which is what the engine's `sean marks` writes.
  const heldEver = [...new Set(receipts.map(o => o.symbol))];
  const closes = heldEver.flatMap(sym => sessions.map(d => [sym, d, priceAt(sym, d)]));

  if (DRY_RUN) {
    console.log(`dry run: method ${METHOD}, plan since ${FIRST}, rotation ${LAST_DECISION}, data ${dataDate}`);
    console.log({ orders: receipts.length, sells: receipts.filter(o => o.side === 'sell').length,
      symbols: heldEver.length, closes: closes.length, equity: equity.length,
      unbought: next.slice(-SKIPPED).map(t => t.symbol).join(', '),
      pnl: equity.at(-1) });
    process.exit(0);
  }

  await c.query('BEGIN');
  await c.query('TRUNCATE sean_own_orders, sean_reminder_marks, sean_link, sean_equity, sean_marks, sean_orders RESTART IDENTITY CASCADE');

  const ids = [];
  for (const o of receipts) {
    const { rows } = await c.query(
      `INSERT INTO sean_orders (image_sha256, side, order_type, status, symbol, executed_at, price, shares,
         amount_usd, trading_fee_usd, regulatory_fee_usd, ppn_usd, total_usd, net_profit_usd, fills, raw)
       VALUES ($1,$2,$3,'Filled',$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,'[]',$14) RETURNING id`,
      [`demo-${String(o.i).padStart(4, '0')}`, o.side, o.orderType, o.symbol, o.executedAt, o.price, o.shares,
        o.amountUsd, o.tradingFeeUsd, o.regulatoryFeeUsd, o.ppnUsd, o.totalUsd, o.netProfitUsd,
        JSON.stringify({ demo: true })]);
    ids[o.i] = rows[0].id;
  }
  await c.query('INSERT INTO sean_own_orders (order_id, note) VALUES ($1, $2)',
    [ids[OWN_NVDA], 'Bought with the PLTR proceeds two minutes earlier: my own, not the plan’s.']);

  for (const [symbol, date, close] of closes)
    await c.query('INSERT INTO sean_marks (symbol, date, close) VALUES ($1,$2,$3) ON CONFLICT DO NOTHING', [symbol, date, close]);

  for (const e of equity)
    await c.query(`INSERT INTO sean_equity (date, value_usd, cost_usd, realized_usd, unrealized_usd, pnl_usd, fees_usd)
      VALUES ($1,$2,$3,$4,$5,$6,$7)`, [e.date, e.value, e.cost, e.realized, e.unrealized, e.pnl, e.fees]);

  await c.query(`INSERT INTO sean_link (id, strategy_id, since, budget_usd, opening_usd) VALUES (1,$1,$2,NULL,$3)`,
    [METHOD, FIRST, 600.0]);
  // One reminder already ticked off by hand, so the Plan shows both states.
  await c.query(`INSERT INTO sean_reminder_marks (strategy_id, session_date, symbol, action) VALUES ($1,$2,$3,'buy')`,
    [METHOD, LAST_DECISION, next.at(-1).symbol]);

  await c.query('COMMIT');
  counts = (await c.query(`SELECT 'sean_orders' AS what, count(*)::int AS n FROM sean_orders
    UNION ALL SELECT 'sean_marks', count(*)::int FROM sean_marks
    UNION ALL SELECT 'sean_equity', count(*)::int FROM sean_equity
    UNION ALL SELECT 'sean_own_orders', count(*)::int FROM sean_own_orders ORDER BY 1`)).rows;
  console.log(`sean demo seeded: ${METHOD} followed since ${FIRST}, last P&L ${equity.at(-1).pnl}`);
} catch (e) {
  await c.query('ROLLBACK').catch(() => {});
  console.error(e.message);
  process.exitCode = 1;
} finally {
  c.release();
  await pool.end();
}
if (counts) console.log(counts);

// Fills Neon with the Seer v2 design's sample data, flagged is_demo so the UI
// warns "Demo data". Dates are relative to now so the demo is never stale.
// Refuses to run once the real engine has written a run or backfilled bars.
import { Pool, neonConfig } from '@neondatabase/serverless';
import ws from 'ws';

neonConfig.webSocketConstructor = ws;
const pool = new Pool({ connectionString: process.env.DATABASE_URL_UNPOOLED });

const RATE = 16530;
const START_USD = +(20_000_000 / RATE).toFixed(4);

// --- dates (ET calendar, weekdays only) -------------------------------------
const etNow = Object.fromEntries(new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', hourCycle: 'h23',
}).formatToParts(new Date()).map(p => [p.type, p.value]));
const addDays = (ymd, n) => { const d = new Date(`${ymd}T12:00:00Z`); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
const weekend = ymd => [0, 6].includes(new Date(`${ymd}T12:00:00Z`).getUTCDay());
const nextWeekday = (ymd, dir) => { let d = addDays(ymd, dir); while (weekend(d)) d = addDays(d, dir); return d; };

const today = `${etNow.year}-${etNow.month}-${etNow.day}`;
let session = !weekend(today) && +etNow.hour < 16 ? today : nextWeekday(today, 1);
const dataDate = nextWeekday(session, -1);
const sessions = [dataDate]; // 66 sessions ending at dataDate, oldest first
while (sessions.length < 66) sessions.unshift(nextWeekday(sessions[0], -1));
const back = n => sessions[sessions.length - 1 - n]; // n sessions before dataDate

// --- deterministic randomness ------------------------------------------------
let seed = 7;
const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;

// --- content -------------------------------------------------------------------
const strategies = [
  ['A', 'A · Quant', 'Mean Reversion', 'sigma', true, false, 1],
  ['B', 'B · ML', 'Gradient-boosted ranker', 'brain-circuit', false, false, 2],
  ['C', 'C · LLM-veto', 'Quant picks, LLM can veto', 'gavel', false, false, 3],
  ['SPY', 'SPY', 'S&P 500, buy and hold', 'landmark', false, true, 4],
];

const picks = [
  [1, 'GE', 'GE Aerospace', 273.18, 271.40, 278.90, 260.15, 1,
    'GE fell three days in a row and now sits below its usual range, while its longer trend is still up. Strategy A buys short dips like this when they have usually recovered within a week. The limit is a little under the last price, so you only buy if it dips further at the open.'],
  [2, 'LRCX', 'Lam Research', 99.64, 98.20, 102.10, 92.35, 3,
    'Chip-equipment stocks sold off and Lam Research dropped more than its peers without news of its own. Past drops of this size have tended to win back part of the move within five sessions. The stop sits below last month’s low.'],
  [3, 'CSCO', 'Cisco Systems', 67.42, 66.85, 68.30, 64.70, 4,
    'Cisco is a steady, slow-moving stock that slipped to the bottom of its two-week range. The target is modest because Cisco rarely moves far. Four shares keep the possible loss in line with the other picks.'],
];

// [symbol, company, shares, entry, current, tp, sl, days held]
const open = [
  ['NVDA', 'Nvidia', 1, 184.20, 186.95, 190.60, 176.80, 5],
  ['AMZN', 'Amazon', 2, 221.50, 218.10, 228.90, 212.40, 3],
  ['KO', 'Coca-Cola', 3, 69.40, 70.05, 71.20, 67.30, 1],
];

// The design's history rows first: [symbol, strategy, entry, exit, shares, reason, sessions ago]
const named = [
  ['MSFT', 'A', 412.30, 421.10, 1, 'tp', 0], ['AMD', 'B', 162.40, 156.90, 2, 'sl', 0],
  ['JPM', 'A', 298.15, 300.02, 2, 'time', 1], ['XOM', 'C', 114.60, 118.40, 3, 'tp', 2],
  ['PLTR', 'B', 178.20, 169.05, 1, 'gap', 3], ['HD', 'A', 401.80, 409.90, 1, 'tp', 4],
  ['INTC', 'C', 36.40, 35.12, 4, 'sl', 5], ['COST', 'A', 912.00, 908.40, 1, 'time', 6],
];
const POOL = [['AAPL', 'Apple', 231], ['META', 'Meta Platforms', 610], ['GOOGL', 'Alphabet', 188], ['ABBV', 'AbbVie', 192],
  ['PEP', 'PepsiCo', 151], ['WMT', 'Walmart', 98], ['QCOM', 'Qualcomm', 167], ['TXN', 'Texas Instruments', 201],
  ['CAT', 'Caterpillar', 389], ['UNH', 'UnitedHealth', 512], ['ORCL', 'Oracle', 176], ['ADBE', 'Adobe', 462],
  ['MRK', 'Merck', 96], ['CVX', 'Chevron', 152], ['BA', 'Boeing', 171], ['NKE', 'Nike', 78]];
const company = Object.fromEntries([...POOL.map(([s, c]) => [s, c]),
  ['MSFT', 'Microsoft'], ['AMD', 'AMD'], ['JPM', 'JPMorgan Chase'], ['XOM', 'Exxon Mobil'], ['PLTR', 'Palantir'],
  ['HD', 'Home Depot'], ['INTC', 'Intel'], ['COST', 'Costco']]);

// Synthetic closed trades per strategy hitting the design's win rate and profit factor.
const targets = { A: [84, 0.58, 1.42, 0.068, 1.1], B: [91, 0.54, 1.21, 0.041, 1.3], C: [47, 0.61, 1.18, 0.032, 0.8], SPY: [0, 0, 0, 0.046, 0.9] };
const closed = named.map(([sym, s, en, ex, sh, reason, ago]) => ({ sym, s, en, ex, sh, reason, exitDate: back(ago) }));
for (const [s, [n, w, pf]] of Object.entries(targets)) {
  const cost = 0.002, avgWin = 0.022; // round-trip cost; losses sized so the net profit factor ≈ target
  const avgLoss = (w * (avgWin - cost)) / ((1 - w) * (pf || 1)) - cost;
  const have = closed.filter(t => t.s === s).length;
  for (let i = have; i < n; i++) {
    const [sym, , base] = POOL[Math.floor(rnd() * POOL.length)];
    const win = rnd() < w;
    const en = +(base * (0.9 + rnd() * 0.2)).toFixed(2);
    const move = (win ? avgWin : -avgLoss) * (0.6 + rnd() * 0.8);
    const reason = win ? (rnd() < 0.8 ? 'tp' : 'time') : (rnd() < 0.7 ? 'sl' : rnd() < 0.5 ? 'time' : 'gap');
    closed.push({ sym, s, en, ex: +(en * (1 + move)).toFixed(2), sh: Math.max(1, Math.floor(300 / en)), reason,
      exitDate: back(7 + Math.floor(rnd() * 56)) });
  }
}

// Equity curves: random walk pinned to each strategy's target return.
const curve = (target, vol) => {
  const w = [0];
  for (let i = 1; i < sessions.length; i++) w.push(w[i - 1] + (rnd() - 0.5) * vol);
  const n = sessions.length - 1;
  return sessions.map((date, i) => [date, START_USD * (1 + (i === 0 ? 0 : (w[i] - w[n] * i / n + target * 100 * i / n) / 100))]);
};

// --- write ---------------------------------------------------------------------
const c = await pool.connect();
try {
  const real = await c.query('SELECT count(*)::int AS n FROM runs WHERE NOT is_demo');
  if (real.rows[0].n > 0) throw new Error('Real engine runs exist; refusing to overwrite with demo data.');
  const bars = await c.query('SELECT count(*)::int AS n FROM bars');
  if (bars.rows[0].n > 100) throw new Error('Real bars exist (backfill ran); refusing to overwrite with demo data.');

  await c.query('BEGIN');
  await c.query('TRUNCATE action_dismissals, orders, equity_snapshots, bars, fx_rates, runs, strategies RESTART IDENTITY CASCADE');

  for (const r of strategies)
    await c.query('INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort) VALUES ($1,$2,$3,$4,$5,$6,$7)', r);

  await c.query(`INSERT INTO runs (started_at, finished_at, status, data_date, session_date, is_demo)
    VALUES (now() - interval '5 minutes', now(), 'success', $1, $2, true)`, [dataDate, session]);
  await c.query('INSERT INTO fx_rates (date, usd_idr) VALUES ($1, $2)', [dataDate, RATE]);

  for (const [slot, sym, name, last, lim, tp, sl, sh, why] of picks) {
    await c.query(`INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, limit_price, tp_price, sl_price, shares, explanation, status)
      VALUES ('A',$1,$2,$3,$4,$5,$6,$7,$8,$9,$10,'pending')`, [session, slot, sym, name, last, lim, tp, sl, sh, why]);
    await c.query('INSERT INTO bars VALUES ($1,$2,$3,$3,$3,$3,1000000)', [sym, dataDate, last]);
  }

  for (const [i, [sym, name, sh, entry, cur, tp, sl, days]] of open.entries()) {
    const fill = back(days - 1);
    await c.query(`INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, limit_price, tp_price, sl_price, shares, status, fill_date, fill_price, days_held)
      VALUES ('A',$1,$2,$3,$4,$5,$5,$6,$7,$8,'open',$1,$5,$9)`, [fill, i + 1, sym, name, entry, tp, sl, sh, days]);
    await c.query('INSERT INTO bars VALUES ($1,$2,$3,$3,$3,$3,1000000)', [sym, dataDate, cur]);
  }

  for (const t of closed) {
    const pnl = (t.ex - t.en) * t.sh - 0.001 * (t.ex + t.en) * t.sh;
    const filled = nextWeekday(t.exitDate, -3);
    const tp = t.reason === 'tp' ? t.ex : +(t.en * 1.025).toFixed(2);
    const sl = t.reason === 'sl' ? t.ex : +(t.en * 0.96).toFixed(2);
    await c.query(`INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, limit_price, tp_price, sl_price, shares, status,
        fill_date, fill_price, days_held, exit_date, exit_price, exit_reason, pnl_usd)
      VALUES ($1,$2,1,$3,$4,$5,$5,$6,$7,$8,'closed',$2,$5,3,$9,$10,$11,$12) ON CONFLICT DO NOTHING`,
      [t.s, filled, t.sym, company[t.sym], t.en, tp, sl, t.sh, t.exitDate, t.ex, t.reason, pnl.toFixed(4)]);
  }

  for (const [s, [, , , ret, vol]] of Object.entries(targets))
    for (const [date, eq] of curve(ret, vol * 3))
      await c.query('INSERT INTO equity_snapshots VALUES ($1,$2,$3,$3)', [s, date, eq.toFixed(4)]);

  await c.query('COMMIT');
  const counts = await c.query(`SELECT status, count(*)::int AS n FROM orders GROUP BY status ORDER BY status`);
  console.log(`demo seeded: session ${session}, data ${dataDate}`, counts.rows);
} catch (e) {
  await c.query('ROLLBACK').catch(() => {});
  throw e;
} finally {
  c.release();
  await pool.end();
}

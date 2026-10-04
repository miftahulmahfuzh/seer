// Fills Neon with demo data in the paper-trading shape (migration 003), flagged is_demo so the
// UI warns "Demo data". Dates are relative to now so the demo is never stale.
// Roster: SPY (champion, buy and hold), A (bracket), F4-MOM12-N20-TREND and F1-SPY-SMA200-M
// (monthly book strategies). 66 sessions ending at the last completed session: day 0 is the
// first, paper start the second, so the demo spans at least three calendar months.
// Refuses to run once the real engine has written a run, backfilled bars or started paper trading.
// `--dry-run` builds every row and prints the counts without connecting.
import { Pool, neonConfig } from '@neondatabase/serverless';
import ws from 'ws';

const DRY_RUN = process.argv.includes('--dry-run');

const RATE = 16530;
const START_USD = +(20_000_000 / RATE).toFixed(4);
const FEE = 0.001; // demo cost per side
const r2 = v => +v.toFixed(2);
const r4 = v => +v.toFixed(4);

// --- dates (ET calendar, weekdays only) -------------------------------------
const etNow = Object.fromEntries(new Intl.DateTimeFormat('en-US', {
  timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', hourCycle: 'h23',
}).formatToParts(new Date()).map(p => [p.type, p.value]));
const addDays = (ymd, n) => { const d = new Date(`${ymd}T12:00:00Z`); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
const weekend = ymd => [0, 6].includes(new Date(`${ymd}T12:00:00Z`).getUTCDay());
const nextWeekday = (ymd, dir) => { let d = addDays(ymd, dir); while (weekend(d)) d = addDays(d, dir); return d; };
const monthOf = ymd => ymd.slice(0, 7);

const today = `${etNow.year}-${etNow.month}-${etNow.day}`;
const session = !weekend(today) && +etNow.hour < 16 ? today : nextWeekday(today, 1);
const dataDate = nextWeekday(session, -1);
const sessions = [dataDate]; // 66 sessions ending at dataDate, oldest first
while (sessions.length < 66) sessions.unshift(nextWeekday(sessions[0], -1));
const LAST = sessions.length - 1;
const back = n => sessions[LAST - n]; // n sessions before dataDate
const DAY0 = sessions[0]; // initial cash snapshot (the session before paper start)
const PAPER_START = sessions[1];

// Monthly book strategies decide on the first session of a month (MONTHLY_HOLD).
const decisions = sessions.map((_, i) => i).filter(i => i >= 1 && monthOf(sessions[i]) !== monthOf(sessions[i - 1]));
if (decisions.length < 2) throw new Error('demo window must hold two month starts');
const FIRST_DECISION = decisions[0];
const LAST_DECISION = decisions[decisions.length - 1];
const pendingDecision = monthOf(session) !== monthOf(dataDate);

// --- deterministic randomness ------------------------------------------------
let seed = 7;
const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;

// --- roster (display rows as in migration 003; params as the `paper` command writes them) ---
const gate = note => ({ passed: false, note });
const strategies = [
  { id: 'SPY', name: 'SPY', sub: 'S&P 500, buy and hold', icon: 'landmark', champion: true, benchmark: true, sort: 1,
    engine: 'benchmark', rulesId: null,
    params: { demo: true, spec: { engine: 'benchmark', symbol: 'SPY' }, digest: null,
      backtest_gate: gate('Benchmark, not a strategy: it has no backtest gate and is never a Seer pick') } },
  { id: 'A', name: 'A · Quant', sub: 'Mean reversion, 5-day brackets', icon: 'sigma', champion: false, benchmark: false, sort: 2,
    engine: 'bracket', rulesId: 'design-v0',
    params: { demo: true, spec: { engine: 'bracket', object: 'STRATEGY_A', rules_id: 'design-v0' }, digest: null,
      backtest_gate: gate('P3 gate failed out of sample (2022-01-03..2026-10-02): -15.0% vs SPY TR +71.9%, PF 0.92, max DD 33.3%') } },
  { id: 'F4-MOM12-N20-TREND', name: 'F4 · Momentum', sub: 'Top 20 by 12-1 momentum, monthly', icon: 'trending-up', champion: false, benchmark: false, sort: 3,
    engine: 'book', rulesId: 'monthly-hold',
    params: { demo: true, spec: { engine: 'book', object: 'FACTOR', registry_id: 'F4-MOM12-N20-TREND', rules_id: 'monthly-hold' }, digest: null,
      backtest_gate: gate('P7a dev window only; failed max DD <= 15% (22.2%)') } },
  { id: 'F1-SPY-SMA200-M', name: 'F1 · Trend', sub: 'SPY above its 200-day average, monthly', icon: 'shield', champion: false, benchmark: false, sort: 4,
    engine: 'book', rulesId: 'monthly-hold',
    params: { demo: true, spec: { engine: 'book', object: 'TIMING', registry_id: 'F1-SPY-SMA200-M', rules_id: 'monthly-hold' }, digest: null,
      backtest_gate: gate('P7a dev window only; failed max DD <= 15% (18.7%) and >= 100 trades (11)') } },
];

// --- SPY closes, one per session ---------------------------------------------
const spy = [];
for (let i = 0, px = 562; i <= LAST; i++) { px *= 1 + (rnd() - 0.46) * 0.014; spy.push(r2(px)); }
const openOf = i => r2(spy[i - 1] * (1 + (rnd() - 0.5) * 0.004)); // session i's open, near the prior close

const snapshots = []; // [strategy, date, cash, equity]
const paperState = []; // [strategy, cash, equity, pendingDecision]
const bookPositions = []; // [strategy, symbol, shares, mark, entryDate, entryPrice, daysHeld, cost, income, stop, take, exitPending]
const bookTargets = []; // [strategy, session, rank, symbol, weight, last, limit, stop, take, explanation]
const bookTrades = []; // [strategy, symbol, entryDate, exitDate, entryPrice, exitPrice, daysHeld, cost, income, pnl, reason]

// --- SPY: whole shares at paper start's open, held, marked at each close -------
{
  const entry = openOf(1);
  const shares = Math.floor(START_USD / (entry * (1 + FEE)));
  const cost = r4(shares * entry * (1 + FEE));
  const cash = r4(START_USD - cost);
  snapshots.push(['SPY', DAY0, START_USD, START_USD]);
  for (let i = 1; i <= LAST; i++) snapshots.push(['SPY', sessions[i], cash, r4(cash + shares * spy[i])]);
  bookPositions.push(['SPY', 'SPY', shares, spy[LAST], PAPER_START, entry, LAST, cost, 0, null, null, false]);
  paperState.push(['SPY', cash, r4(cash + shares * spy[LAST]), false]);
}

// --- F1: cash until the first month start, then all-in SPY (whole shares) -----
{
  const id = 'F1-SPY-SMA200-M';
  const entry = openOf(FIRST_DECISION);
  const shares = Math.floor(START_USD / (entry * (1 + FEE)));
  const cost = r4(shares * entry * (1 + FEE));
  const cash = r4(START_USD - cost);
  for (let i = 0; i <= LAST; i++)
    snapshots.push(i < FIRST_DECISION ? [id, sessions[i], START_USD, START_USD] : [id, sessions[i], cash, r4(cash + shares * spy[i])]);
  bookPositions.push([id, 'SPY', shares, spy[LAST], sessions[FIRST_DECISION], entry, LAST - FIRST_DECISION + 1, cost, 0, null, null, false]);
  const why = 'SPY closed above its 200-day average, so F1 holds SPY for the month.';
  for (const d of decisions) bookTargets.push([id, sessions[d], 1, 'SPY', 1, spy[d - 1], null, null, null, why]);
  if (pendingDecision) bookTargets.push([id, session, 1, 'SPY', 1, spy[LAST], null, null, null, why]);
  paperState.push([id, cash, r4(cash + shares * spy[LAST]), pendingDecision]);
}

// --- equity curve: random walk pinned to a target return, flat before `from` ---
const curve = (target, vol, from = 1) => {
  const w = [0];
  for (let i = 1; i <= LAST; i++) w.push(w[i - 1] + (rnd() - 0.5) * vol);
  const span = LAST - from;
  return sessions.map((_, i) => {
    if (i < from) return START_USD;
    const k = i - from;
    const wk = w[i] - w[from];
    const wn = w[LAST] - w[from];
    return r4(START_USD * (1 + (wk - wn * k / span + target * 100 * k / span) / 100));
  });
};

// --- F4: 12 names (MONTHLY_HOLD buys whole shares, so names over ~$60 do not fit) ------
{
  const id = 'F4-MOM12-N20-TREND';
  const eq = curve(0.031, 2.4, FIRST_DECISION);
  const E = eq[LAST];
  // [symbol, mark, held since the first decision?]
  const HELD = [['INTC', 36.42, true], ['PFE', 25.08, false], ['F', 11.31, true], ['T', 27.64, true], ['BAC', 47.18, false],
    ['WBD', 12.37, true], ['KMI', 27.93, false], ['HPE', 22.46, true], ['CMCSA', 32.81, false], ['CSX', 33.57, true],
    ['CCL', 28.44, false], ['HBAN', 16.72, true]];
  let invested = 0;
  HELD.forEach(([sym, mark, early], rank) => {
    const from = early ? FIRST_DECISION : LAST_DECISION;
    const entry = r2(mark / (1 + (rnd() - 0.4) * 0.15));
    const shares = Math.max(1, Math.floor((0.05 * E) / mark));
    invested += shares * mark;
    bookPositions.push([id, sym, shares, mark, sessions[from], entry, LAST - from + 1, r4(shares * entry * (1 + FEE)), 0, null, null, false]);
    bookTargets.push([id, sessions[LAST_DECISION], rank + 1, sym, 0.05, r2(mark * (1 + (rnd() - 0.5) * 0.04)), null, null, null,
      rank === 0 ? `${sym} ranks first by 12-1 momentum among index members, and SPY is above its 200-day average.` : null]);
    if (pendingDecision) bookTargets.push([id, session, rank + 1, sym, 0.05, mark, null, null, null, null]);
  });
  // The first decision's targets: the early names, five sold at the last decision (their rank
  // fell), and one closed by force when it left the index and its bars stopped.
  const firstTargets = HELD.filter(([, , early]) => early).map(([sym, mark]) => [sym, r2(mark * 0.97)]);
  const SOLD = [['KEY', 18.2], ['RF', 25.3], ['NCLH', 24.1], ['KHC', 26.4], ['VZ', 41.7]];
  for (const [sym, en] of SOLD) {
    const ex = r2(en * (1 + (rnd() - 0.55) * 0.16));
    const shares = Math.max(1, Math.floor((0.05 * START_USD) / en));
    const cost = r4(shares * en * (1 + FEE)), income = r4(shares * ex * (1 - FEE));
    firstTargets.push([sym, en]);
    bookTrades.push([id, sym, sessions[FIRST_DECISION], sessions[LAST_DECISION], en, ex, LAST_DECISION - FIRST_DECISION + 1, cost, income, r4(income - cost), 'signal']);
  }
  {
    const at = Math.min(LAST - 1, FIRST_DECISION + 12);
    const en = 10.9, ex = 10.25, shares = Math.floor((0.05 * START_USD) / en);
    const cost = r4(shares * en * (1 + FEE)), income = r4(shares * ex * (1 - FEE));
    firstTargets.push(['WBA', en]);
    bookTrades.push([id, 'WBA', sessions[FIRST_DECISION], sessions[at], en, ex, at - FIRST_DECISION + 1, cost, income, r4(income - cost), 'forced']);
  }
  firstTargets.forEach(([sym, last], k) => bookTargets.push([id, sessions[FIRST_DECISION], k + 1, sym, 0.05, last, null, null, null, null]));
  const cashShare = Math.max(0, 1 - invested / E);
  eq.forEach((e, i) => snapshots.push([id, sessions[i], i < FIRST_DECISION ? e : r4(e * cashShare), e]));
  paperState.push([id, r4(E - invested), E, pendingDecision]);
}

// --- A: bracket orders ---------------------------------------------------------
const picks = [
  [1, 'GE', 'GE Aerospace', 273.18, 271.40, 278.90, 260.15, 1,
    'GE fell three days in a row and now sits below its usual range, while its longer trend is still up. Strategy A buys short dips like this when they have usually recovered within a week. The limit is a little under the last price, so it only buys if the price dips further at the open.'],
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

// The design's history rows first: [symbol, entry, exit, shares, reason, sessions ago]
const named = [
  ['MSFT', 412.30, 421.10, 1, 'tp', 0], ['JPM', 298.15, 300.02, 2, 'time', 1],
  ['HD', 401.80, 409.90, 1, 'tp', 4], ['COST', 912.00, 908.40, 1, 'time', 6],
];
const POOL = [['AAPL', 'Apple', 231], ['META', 'Meta Platforms', 610], ['GOOGL', 'Alphabet', 188], ['ABBV', 'AbbVie', 192],
  ['PEP', 'PepsiCo', 151], ['WMT', 'Walmart', 98], ['QCOM', 'Qualcomm', 167], ['TXN', 'Texas Instruments', 201],
  ['CAT', 'Caterpillar', 389], ['UNH', 'UnitedHealth', 512], ['ORCL', 'Oracle', 176], ['ADBE', 'Adobe', 462],
  ['MRK', 'Merck', 96], ['CVX', 'Chevron', 152], ['BA', 'Boeing', 171], ['NKE', 'Nike', 78]];
const company = Object.fromEntries([...POOL.map(([s, c]) => [s, c]),
  ['MSFT', 'Microsoft'], ['JPM', 'JPMorgan Chase'], ['HD', 'Home Depot'], ['COST', 'Costco']]);

// Closed trades: exits within the paper window (fills at least three sessions after paper start).
const closed = named.map(([sym, en, ex, sh, reason, ago]) => ({ sym, en, ex, sh, reason, exitDate: back(ago) }));
{
  const [n, w, pf] = [38, 0.53, 1.12];
  const cost = 0.002, avgWin = 0.022; // round-trip cost; losses sized so the net profit factor ≈ target
  const avgLoss = (w * (avgWin - cost)) / ((1 - w) * pf) - cost;
  for (let i = closed.length; i < n; i++) {
    const [sym, , base] = POOL[Math.floor(rnd() * POOL.length)];
    const win = rnd() < w;
    const en = r2(base * (0.9 + rnd() * 0.2));
    const move = (win ? avgWin : -avgLoss) * (0.6 + rnd() * 0.8);
    const reason = win ? (rnd() < 0.8 ? 'tp' : 'time') : (rnd() < 0.7 ? 'sl' : rnd() < 0.5 ? 'time' : 'gap');
    closed.push({ sym, en, ex: r2(en * (1 + move)), sh: Math.max(1, Math.floor(300 / en)), reason, exitDate: back(7 + Math.floor(rnd() * 52)) });
  }
}
{
  const eq = curve(0.021, 3.3);
  const held = open.reduce((a, [, , sh, , cur]) => a + sh * cur, 0);
  eq.forEach((e, i) => snapshots.push(['A', sessions[i], i === 0 ? e : r4(e - (i === LAST ? held : 0)), e]));
  paperState.push(['A', r4(eq[LAST] - held), eq[LAST], false]);
}

const rows = { strategies, snapshots, paperState, bookPositions, bookTargets, bookTrades, picks, open, closed };

if (DRY_RUN) {
  const months = [...new Set(sessions.map(monthOf))];
  console.log(`dry run: day 0 ${DAY0}, paper start ${PAPER_START}, data ${dataDate}, session ${session}`);
  console.log(`months ${months.join(', ')}; decisions ${decisions.map(i => sessions[i]).join(', ')}; pending decision ${pendingDecision}`);
  console.log(Object.fromEntries(Object.entries(rows).map(([k, v]) => [k, v.length])));
  process.exit(0);
}

// --- write ---------------------------------------------------------------------
neonConfig.webSocketConstructor = ws;
const pool = new Pool({ connectionString: process.env.DATABASE_URL_UNPOOLED });
const c = await pool.connect();
try {
  const real = await c.query('SELECT count(*)::int AS n FROM runs WHERE NOT is_demo');
  if (real.rows[0].n > 0) throw new Error('Real engine runs exist; refusing to overwrite with demo data.');
  const bars = await c.query('SELECT count(*)::int AS n FROM bars');
  if (bars.rows[0].n > 100) throw new Error('Real bars exist (backfill ran); refusing to overwrite with demo data.');
  const paper = await c.query('SELECT count(*)::int AS n FROM paper_state WHERE NOT EXISTS (SELECT 1 FROM runs WHERE is_demo)');
  if (paper.rows[0].n > 0) throw new Error('Real paper state exists; refusing to overwrite with demo data.');

  await c.query('BEGIN');
  await c.query(`TRUNCATE action_dismissals, orders, equity_snapshots, bars, fx_rates, runs, paper_state, book_positions,
    book_targets, book_fills, book_trades, dividends, strategies RESTART IDENTITY CASCADE`);

  for (const s of strategies)
    await c.query(`INSERT INTO strategies (id, name, sub, icon, is_champion, is_benchmark, sort, engine, rules_id, paper_start, params)
      VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)`,
    [s.id, s.name, s.sub, s.icon, s.champion, s.benchmark, s.sort, s.engine, s.rulesId, PAPER_START, JSON.stringify(s.params)]);

  await c.query(`INSERT INTO runs (started_at, finished_at, status, data_date, session_date, is_demo, paper_status, paper_finished_at)
    VALUES (now() - interval '5 minutes', now() - interval '2 minutes', 'success', $1, $2, true, 'success', now())`, [dataDate, session]);
  await c.query('INSERT INTO fx_rates (date, usd_idr) VALUES ($1, $2)', [dataDate, RATE]);

  for (const [slot, sym, name, last, lim, tp, sl, sh, why] of picks) {
    await c.query(`INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, limit_price, tp_price, sl_price, shares, explanation, status)
      VALUES ('A',$1,$2,$3,$4,$5,$6,$7,$8,$9,$10,'pending')`, [session, slot, sym, name, last, lim, tp, sl, sh, why]);
    await c.query('INSERT INTO bars VALUES ($1,$2,$3,$3,$3,$3,1000000)', [sym, dataDate, last]);
  }

  for (const [i, [sym, name, sh, entry, cur, tp, sl, days]] of open.entries()) {
    const fill = back(days - 1);
    await c.query(`INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, limit_price, tp_price, sl_price, shares, status, fill_date, fill_price, days_held, mark)
      VALUES ('A',$1,$2,$3,$4,$5,$5,$6,$7,$8,'open',$1,$5,$9,$10)`, [fill, i + 1, sym, name, entry, tp, sl, sh, days, cur]);
    await c.query('INSERT INTO bars VALUES ($1,$2,$3,$3,$3,$3,1000000)', [sym, dataDate, cur]);
  }
  await c.query('INSERT INTO bars VALUES ($1,$2,$3,$3,$3,$3,1000000)', ['SPY', dataDate, spy[LAST]]);

  for (const t of closed) {
    const pnl = (t.ex - t.en) * t.sh - FEE * (t.ex + t.en) * t.sh;
    const filled = nextWeekday(t.exitDate, -3);
    const tp = t.reason === 'tp' ? t.ex : r2(t.en * 1.025);
    const sl = t.reason === 'sl' ? t.ex : r2(t.en * 0.96);
    await c.query(`INSERT INTO orders (strategy_id, session_date, slot, symbol, company, last_price, limit_price, tp_price, sl_price, shares, status,
        fill_date, fill_price, days_held, exit_date, exit_price, exit_reason, pnl_usd)
      VALUES ('A',$1,1,$2,$3,$4,$4,$5,$6,$7,'closed',$1,$4,3,$8,$9,$10,$11) ON CONFLICT DO NOTHING`,
    [filled, t.sym, company[t.sym], t.en, tp, sl, t.sh, t.exitDate, t.ex, t.reason, pnl.toFixed(4)]);
  }

  for (const r of snapshots) await c.query('INSERT INTO equity_snapshots (strategy_id, date, cash_usd, equity_usd) VALUES ($1,$2,$3,$4)', r);

  for (const [id, cash, equity, decision] of paperState)
    await c.query(`INSERT INTO paper_state (strategy_id, last_session, cash_usd, equity_usd, initial_cash_usd, usd_idr, pending_session, pending_decision)
      VALUES ($1,$2,$3,$4,$5,$6,$7,$8)`, [id, dataDate, cash, equity, START_USD, RATE, session, decision]);

  for (const r of bookPositions)
    await c.query(`INSERT INTO book_positions (strategy_id, symbol, shares, mark, entry_date, entry_price, days_held, cost_usd, income_usd,
        stop_price, take_price, exit_pending) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)`, r);

  for (const r of bookTargets)
    await c.query(`INSERT INTO book_targets (strategy_id, session_date, rank, symbol, weight, last_price, limit_price, stop_price, take_price, explanation)
      VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)`, r);

  for (const r of bookTrades)
    await c.query(`INSERT INTO book_trades (strategy_id, symbol, entry_date, exit_date, entry_price, exit_price, days_held, cost_usd, income_usd,
        pnl_usd, exit_reason) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)`, r);

  await c.query('COMMIT');
  const counts = await c.query(`SELECT 'orders ' || status AS what, count(*)::int AS n FROM orders GROUP BY status
    UNION ALL SELECT 'book_positions', count(*)::int FROM book_positions
    UNION ALL SELECT 'book_trades', count(*)::int FROM book_trades
    UNION ALL SELECT 'equity_snapshots', count(*)::int FROM equity_snapshots ORDER BY what`);
  console.log(`demo seeded: paper start ${PAPER_START}, session ${session}, data ${dataDate}`, counts.rows);
} catch (e) {
  await c.query('ROLLBACK').catch(() => {});
  throw e;
} finally {
  c.release();
  await pool.end();
}

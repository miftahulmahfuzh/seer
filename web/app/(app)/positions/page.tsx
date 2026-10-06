import { Crown, Gavel, Landmark, TriangleAlert } from 'lucide-react';
import { AppHeader } from '@/components/AppHeader';
import { PaperChip } from '@/components/PaperChip';
import { selectStrategy, sharesLabel, strategyIcon } from '@/components/roster';
import { StrategySwitch } from '@/components/StrategySwitch';
import { WhyToggle } from '@/components/WhyToggle';
import {
  pendingOrders, positions as getPositions, runStatus, strategies, vetoes as getVetoes,
  type Holding, type Pending, type PendingOrder, type RunStatus, type Strategy, type Veto,
} from '@/lib/data';
import { companyName, monthDay, pct, shortDate, signedPct, signedRp, signedUsd, usd } from '@/lib/format';
import { wibDate } from '@/lib/session';
import { cardBg } from '@/lib/slots';
import { checkedLine, headlinesLabel, noCheckLine, vetoSheet, type VetoSheet } from '@/lib/vetoes';
import s from './positions.module.css';

export const dynamic = 'force-dynamic';

type Search = { s?: string };

const NO_PENDING: Pending = { sessionDate: null, decision: false, orders: [] };

export default async function Positions({ searchParams }: { searchParams: Promise<Search> }) {
  const now = new Date();
  const q = await searchParams;
  const [roster, run] = await Promise.all([strategies(), runStatus(now)]);
  const strat = selectStrategy(roster, q.s);
  // Paper orders exist for research strategies only; hidden while the data is stale.
  const showOrders = !!strat && !strat.isBenchmark && !run.stale;
  const [open, pending] = await Promise.all([
    strat ? getPositions(strat.id) : Promise.resolve([] as Holding[]),
    showOrders && strat ? pendingOrders(strat.id) : Promise.resolve(NO_PENDING),
  ]);

  const bracket = open.filter(p => p.kind === 'bracket');
  const book = open.filter(p => p.kind !== 'bracket');
  const pnl = open.reduce((a, p) => a + p.pnl, 0);
  const exitsToday = bracket.filter(p => p.maxDays !== null && p.day >= p.maxDays).length + book.filter(p => p.exitPending).length;
  const invested = book.reduce((a, p) => a + (p.weight ?? 0), 0);
  const holdsBook = strat?.engine === 'book' || strat?.engine === 'benchmark';
  const paper = !!strat && strat.isPaper;
  const paperWarn = !!run.sessionDate && run.paperStatus !== 'success';
  const StratIcon = strat ? strategyIcon(strat.icon) : Landmark;
  const href = (id: string) => `/positions?s=${encodeURIComponent(id)}`;
  const [noneTitle, noneSub] = emptyState(strat);
  const orderSession = showOrders ? pending.sessionDate : null;
  // The news check's verdicts for the same session (C, handover D10). Read only for a strategy that runs
  // the check: its roster row comes from migration 004, which also creates news_vetoes.
  const showChecks = !!strat && !!orderSession && strat.checksNews && strat.engine === 'bracket';
  const checks = showChecks && strat && orderSession ? await getVetoes(strat.id, orderSession) : [];
  const sheet = showChecks ? vetoSheet(checks) : null;

  return (
    <>
      <AppHeader date={shortDate(wibDate(now))} title="Positions" demo={run.isDemo} />
      <div className="stack">
        <section className={`sheet bg-sheet ${s.summary}`}>
          <div className={s.between}>
            <span className="eyebrow">Unrealized P/L</span>
            <span className="pill-outline">
              {strat?.isChampion ? <Crown size={15} /> : <StratIcon size={15} />}
              {strat?.name ?? '—'}
            </span>
          </div>
          {strat && <StrategySwitch strategies={roster} current={strat.id} href={href} label="Strategy" />}
          <div className={s.stats}>
            <div className={`${s.stat} ${pnl < 0 ? 'neg' : 'pos'}`}>
              <span className={`num ${s.big}`}>{signedUsd(pnl)}</span>
              <span className={s.sub}>{signedRp(pnl, run.usdIdr)}</span>
            </div>
            <div className={s.stat}><span className={s.mid}>{open.length}</span><span className={s.sub}>Open</span></div>
            {holdsBook ? (
              <div className={s.stat}><span className={`num ${s.mid}`}>{pct(invested, 0)}</span><span className={s.sub}>Invested</span></div>
            ) : (
              <div className={s.stat}><span className={s.mid}>{exitsToday}</span><span className={s.sub}>Exits today</span></div>
            )}
          </div>
          {paper && strat && (
            <div className={s.paperLine}><PaperChip /><span>{paperNote(strat)}</span></div>
          )}
        </section>

        {paperWarn && run.sessionDate && (
          <section className={`sheet over bg-coral ${s.warn}`} role="status">
            <div className={s.warnHead}>
              <span className={s.warnIcon} aria-hidden="true"><TriangleAlert size={22} /></span>
              <span className="eyebrow">Paper step</span>
            </div>
            <span className={s.warnText}>{paperWarning(run.paperStatus, run.sessionDate)}</span>
          </section>
        )}

        {open.length === 0 ? (
          <section className={`sheet over bg-stone ${s.none}`}>
            <span>{noneTitle}</span>
            {noneSub && <span className={s.noneSub}>{noneSub}</span>}
          </section>
        ) : (
          <div className={s.grid}>
            {bracket.map((p, i) => <BracketCard key={p.key} q={p} bg={cardBg(p.slot, i)} paper={paper} />)}
            {book.map((p, i) => p.kind === 'benchmark'
              ? <BenchmarkCard key={p.key} q={p} />
              : <BookCard key={p.key} q={p} bg={cardBg(null, bracket.length + i)} paper={paper} />)}
          </div>
        )}

        {strat && orderSession && (
          <section className={`sheet over bg-sheet ${s.orders}`}>
            <div className={s.between}>
              <span className="eyebrow">Paper orders for {shortDate(orderSession)}</span>
              {paper && <PaperChip />}
            </div>
            {pending.orders.some(o => o.kind === 'book') && <span className={s.ordersSub}>Target portfolio after the open, by rank</span>}
            {pending.orders.length === 0 ? (
              <span className={s.ordersNone}>{noOrders(strat, pending, sheet)}</span>
            ) : (
              <ul className={s.orderList}>
                {pending.orders.map(o => <OrderRow key={o.key} o={o} />)}
              </ul>
            )}
          </section>
        )}

        {strat && orderSession && sheet && <VetoedTonight st={strat} session={orderSession} sheet={sheet} />}
        <div className="nav-clear" />
      </div>
    </>
  );
}

function paperNote(st: Strategy): string {
  const since = st.paperStart ? `On paper since ${shortDate(st.paperStart)}.` : 'Paper trading starts with the next nightly run.';
  return `${since} Simulated orders, no real money.`;
}

function paperWarning(status: RunStatus['paperStatus'], session: string): string {
  const day = shortDate(session);
  if (status === 'failed') return `Paper trading failed for ${day}. Paper positions and orders are from the night before.`;
  if (status === 'running') return `Paper trading for ${day} is still running. Paper positions may be a night old.`;
  return `Paper trading has not run for ${day} yet. Paper positions may be a night old.`;
}

function emptyState(st: Strategy | null): [string, string | null] {
  if (!st) return ['No strategies yet.', null];
  if (st.engine === 'benchmark') return ['Not bought yet.', `${st.name} is bought at the open of the first paper session.`];
  if (st.engine === 'book') return ['In cash.', `${st.short} decides on the first session of each month.`];
  return ['No open positions.', null];
}

function noOrders(st: Strategy, p: Pending, sheet: VetoSheet | null): string {
  if (st.engine === 'book') {
    return p.decision
      ? `No orders. ${st.short} decided to hold cash.`
      : `No orders. ${st.short} decides on the first session of each month.`;
  }
  if (sheet && sheet.state === 'missing') return `No orders. ${st.short} buys nothing this session.`;
  if (sheet && sheet.state === 'failed') return `No orders. ${st.short} sits this session out.`;
  if (sheet && sheet.allowed === 0) return 'No orders. Nothing passed the news check.';
  return 'No setups tonight. Cash is a position.';
}

/**
 * "Vetoed tonight" (handover D10): what the news check took out of A's picks for this session.
 * A failed check is no trade (design §8), so failed rows are listed with the vetoes.
 */
function VetoedTonight({ st, session, sheet }: { st: Strategy; session: string; sheet: VetoSheet }) {
  return (
    <section className={`sheet over bg-stone ${s.vetoes}`}>
      <div className={`${s.between} ${s.vetoHead}`}>
        <span className="eyebrow">Vetoed tonight</span>
        {sheet.state !== 'missing' && (
          <span className={`chip num ${s.vetoCount}`}>{checkedLine(sheet.checked, sheet.state === 'listed' ? sheet.allowed : 0)}</span>
        )}
      </div>
      {sheet.state === 'missing' && (
        <span className={s.ordersNone}>{noCheckLine(shortDate(session), st.short)}</span>
      )}
      {sheet.state === 'failed' && (
        <>
          <span className={s.ordersNone}>News check failed for {shortDate(session)}: {st.short} sits this session out.</span>
          <span className={s.vetoReason}>{sheet.reason}</span>
        </>
      )}
      {sheet.state === 'listed' && (sheet.rows.length === 0 ? (
        <span className={s.ordersNone}>Nothing vetoed. Every pick passed the news check.</span>
      ) : (
        <ul className={s.orderList}>
          {sheet.rows.map(v => <VetoRow key={v.symbol} v={v} />)}
        </ul>
      ))}
    </section>
  );
}

function VetoRow({ v }: { v: Veto }) {
  const veto = v.verdict === 'veto';
  const facts = headlinesLabel(v.headlineCount) + (v.earningsDate ? ` · earnings ${monthDay(v.earningsDate)}` : '');
  return (
    <li className={s.order}>
      <div className={s.orderHead}>
        <span className={s.rank} data-tip="Rank among A's picks">{v.rank}</span>
        <span className={s.orderSym}>{v.symbol}</span>
        <span className={s.vetoGap} />
        {veto ? (
          <span className={`chip ${s.vetoChip}`} data-tip="The LLM vetoed this pick on its news">
            <Gavel size={15} aria-hidden="true" />Veto
          </span>
        ) : (
          <span className={`chip ${s.failChip}`} data-tip="The news check failed, so no trade (design §8)">
            <TriangleAlert size={15} aria-hidden="true" />Failed
          </span>
        )}
      </div>
      <span className={s.vetoFacts}>{facts}</span>
      <WhyToggle text={v.reason.trim() === '' ? null : v.reason} label={veto ? 'Why vetoed' : 'Why it failed'}
        missing="No reason was stored for this check." />
    </li>
  );
}

function Change({ pnl, ratio }: { pnl: number; ratio: number | null }) {
  return (
    <div className={`${s.change} ${pnl < 0 ? 'neg' : 'pos'}`}>
      <span className={`num ${s.pct}`}>{ratio === null ? '—' : signedPct(ratio)}</span>
      <span className="num">{signedUsd(pnl)}</span>
    </div>
  );
}

function Range({ stop, target, entry, current }: { stop: number; target: number; entry: number; current: number }) {
  const span = target - stop;
  const at = (v: number) => (span > 0 ? Math.min(100, Math.max(0, ((v - stop) / span) * 100)) : 50);
  const e = at(entry), c = at(current), up = current >= entry;
  return (
    <div className={s.range}>
      <div className={`num ${s.between} ${s.rangeLabels}`}><span>Stop {usd(stop)}</span><span>Target {usd(target)}</span></div>
      <div className={s.track} role="img" aria-label={`Price is ${Math.round(c)}% of the way from stop to target`}>
        <div className={s.fill} style={{ left: `${Math.min(e, c)}%`, width: `${Math.abs(c - e)}%`, background: up ? 'var(--pos)' : 'var(--neg)' }} />
        <div className={s.entry} style={{ left: `${e}%` }} />
        <div className={s.cur} style={{ left: `${c}%` }} />
      </div>
    </div>
  );
}

function Weight({ weight, label }: { weight: number | null; label: string }) {
  if (weight === null) return null;
  const w = Math.min(1, Math.max(0, weight));
  return (
    <div className={s.weight}>
      <div className={`num ${s.between} ${s.rangeLabels}`}><span>{pct(w, 1)} {label}</span></div>
      <div className={s.track} role="img" aria-label={`${pct(w, 1)} ${label}`}>
        <div className={s.weightFill} style={{ width: `${w * 100}%` }} />
      </div>
    </div>
  );
}

function StopTarget({ q }: { q: Holding }) {
  if (q.sl !== null && q.tp !== null) return <Range stop={q.sl} target={q.tp} entry={q.entry} current={q.current} />;
  if (q.sl === null && q.tp === null) return null;
  return (
    <div className={s.chips}>
      {q.sl !== null && <span className="chip num">Stop {usd(q.sl)}</span>}
      {q.tp !== null && <span className="chip num">Target {usd(q.tp)}</span>}
    </div>
  );
}

function BracketCard({ q, bg, paper }: { q: Holding; bg: string; paper: boolean }) {
  const max = q.maxDays ?? 5;
  return (
    <article className={`sheet over ${bg} ${s.card}`}>
      <div className={s.head}>
        <div className={s.ticker}>
          <span className={s.sym}>{q.symbol}</span>
          <span className={s.company}>{companyName(q.company, q.symbol) ? `${q.company} · ` : ''}{sharesLabel(q.shares)}</span>
        </div>
        <Change pnl={q.pnl} ratio={q.pnlPct} />
      </div>
      <div className={s.chips}>
        {paper && <PaperChip />}
        <span className="chip num">Entry {usd(q.entry)}</span>
        <span className={`chip num ${s.now}`}>Now {usd(q.current)}</span>
      </div>
      <StopTarget q={q} />
      <div className={s.between}>
        <div className={s.days} aria-hidden="true">
          {Array.from({ length: max }, (_, k) => k + 1).map(k => <span key={k} className={k <= q.day ? s.dayOn : s.dayOff} />)}
        </div>
        <span className={s.dayLabel}>{q.day >= max ? `Day ${q.day}/${max} · exit today` : `Day ${q.day}/${max}`}</span>
      </div>
    </article>
  );
}

function BookCard({ q, bg, paper }: { q: Holding; bg: string; paper: boolean }) {
  return (
    <article className={`sheet over ${bg} ${s.card}`}>
      <div className={s.head}>
        <div className={s.ticker}>
          <span className={s.sym}>{q.symbol}</span>
          <span className={s.company}>{companyName(q.company, q.symbol) ? `${q.company} · ` : ''}{sharesLabel(q.shares)}</span>
        </div>
        <Change pnl={q.pnl} ratio={q.pnlPct} />
      </div>
      <div className={s.chips}>
        {paper && <PaperChip />}
        <span className="chip num">Entry {usd(q.entry)}</span>
        <span className={`chip num ${s.now}`}>Now {usd(q.current)}</span>
      </div>
      <StopTarget q={q} />
      <Weight weight={q.weight} label="of paper equity" />
      <div className={s.between}>
        <span className={s.held}>{q.exitPending ? 'Sells at the next open' : 'Held until the rules say sell'}</span>
        <span className={s.dayLabel}>{q.day === 1 ? 'Day 1' : `${q.day} days held`}</span>
      </div>
    </article>
  );
}

function BenchmarkCard({ q }: { q: Holding }) {
  return (
    <article className={`sheet over bg-stone ${s.card}`}>
      <div className={s.head}>
        <div className={s.ticker}>
          <span className={s.sym}>{q.symbol}</span>
          <span className={s.company}>{companyName(q.company, q.symbol) ? `${q.company} · ` : ''}{sharesLabel(q.shares)}</span>
        </div>
        <Change pnl={q.pnl} ratio={q.pnlPct} />
      </div>
      <div className={s.chips}>
        <span className={`chip ${s.benchChip}`} data-tip="The yardstick every paper strategy is measured against">
          <Landmark size={15} aria-hidden="true" />Benchmark
        </span>
        <span className="chip num">Entry {usd(q.entry)}</span>
        <span className={`chip num ${s.now}`}>Now {usd(q.current)}</span>
      </div>
      <Weight weight={q.weight} label="invested" />
      <div className={s.between}>
        <span className={s.held}>Buy and hold, dividends reinvested</span>
        <span className={s.dayLabel}>{q.day === 1 ? 'Day 1' : `${q.day} days held`}</span>
      </div>
    </article>
  );
}

function OrderRow({ o }: { o: PendingOrder }) {
  const cells: [string, string][] = o.kind === 'bracket'
    ? [
        ['Limit', o.limit === null ? '—' : usd(o.limit)],
        ['Target', o.tp === null ? '—' : usd(o.tp)],
        ['Stop', o.sl === null ? '—' : usd(o.sl)],
        ['Shares', o.shares === null ? '—' : String(o.shares)],
      ]
    : [
        ['Weight', o.weight === null ? '—' : pct(o.weight, 1)],
        ['Limit', o.limit === null ? 'Open' : usd(o.limit)],
        ['Stop', o.sl === null ? '—' : usd(o.sl)],
        ['Target', o.tp === null ? '—' : usd(o.tp)],
      ];
  return (
    <li className={s.order}>
      <div className={s.orderHead}>
        {o.kind === 'book' && <span className={s.rank}>{o.rank}</span>}
        <span className={s.orderSym}>{o.symbol}</span>
        <span className={s.orderCo}>{companyName(o.company, o.symbol) ? `${o.company} · ` : ''}last {usd(o.last)}</span>
      </div>
      <OrderCells cells={cells} />
      <WhyToggle text={o.explanation} />
    </li>
  );
}

function OrderCells({ cells }: { cells: [string, string][] }) {
  return (
    <dl className={s.cells}>
      {cells.map(([k, v]) => (
        <div key={k} className={s.cell}><dt>{k}</dt><dd className="num">{v}</dd></div>
      ))}
    </dl>
  );
}

import { Clock, Crown, Gavel, Landmark, Pause, TriangleAlert } from 'lucide-react';
import { AppHeader } from '@/components/AppHeader';
import { PaperChip } from '@/components/PaperChip';
import { selectStrategy, sharesLabel, strategyIcon } from '@/components/roster';
import { StrategySwitch } from '@/components/StrategySwitch';
import { WhyToggle } from '@/components/WhyToggle';
import { heldUsd, orderSizeChange, picksMonthlySizesWeekly, sizeLabel, sizeTip, type SizeChange } from '@/lib/cadence';
import {
  bookPreview, pendingOrders, positions as getPositions, runStatus, strategies, vetoes as getVetoes,
  type Holding, type Pending, type PendingOrder, type Preview, type RunStatus, type Strategy, type Veto,
} from '@/lib/data';
import {
  PAPER_PAUSED, panelState, pipelineState, timing,
  type PanelState, type PipelineState, type Timing,
} from '@/lib/decision';
import { companyName, monthDay, pct, shortDate, signedPct, signedRp, signedUsd, usd } from '@/lib/format';
import { wibDate, wibTime } from '@/lib/session';
import { cardBg } from '@/lib/slots';
import { checkedLine, headlinesLabel, noCheckLine, vetoSheet, type VetoSheet } from '@/lib/vetoes';
import s from './positions.module.css';

export const dynamic = 'force-dynamic';

type Search = { s?: string };

const NO_PENDING: Pending = { sessionDate: null, decision: false, orders: [], equity: null };
const NO_PREVIEW: Preview = { dataDate: null, picks: [] };

export default async function Positions({ searchParams }: { searchParams: Promise<Search> }) {
  const now = new Date();
  const q = await searchParams;
  const [roster, run] = await Promise.all([strategies(), runStatus(now)]);
  const strat = selectStrategy(roster, q.s);
  // Paper orders exist for research strategies only. They are now fetched whatever session they are
  // for: an expired decision is shown as a spent record (handover Q5), never left as a blank panel.
  const asksOrders = !!strat && !strat.isBenchmark;
  const [open, pending, preview] = await Promise.all([
    strat ? getPositions(strat.id) : Promise.resolve([] as Holding[]),
    asksOrders && strat ? pendingOrders(strat.id) : Promise.resolve(NO_PENDING),
    asksOrders && strat?.engine === 'book' ? bookPreview(strat.id) : Promise.resolve(NO_PREVIEW),
  ]);

  // Which of the five the blank used to be (web/lib/decision.ts). `panel` is this strategy's own
  // decision; `pipeline` is the nightly behind it; the paused note is page-level and sits above both.
  const when = timing(now);
  // The fourth argument is D9.6 and is NOT optional here, whatever its default says: a retired
  // strategy's pending row is a record, never an instruction. Drop it and a superseded entry
  // renders a live order on the night its successor starts.
  const panel = panelState(pending.sessionDate, pending.decision, now, strat?.status === 'retired');
  const pipeline = pipelineState(run.sessionDate, run.finishedAt, now);
  const live = asksOrders && panel === 'live';

  const bracket = open.filter(p => p.kind === 'bracket');
  const book = open.filter(p => p.kind !== 'bracket');
  const pnl = open.reduce((a, p) => a + p.pnl, 0);
  const exitsToday = bracket.filter(p => p.maxDays !== null && p.day >= p.maxDays).length + book.filter(p => p.exitPending).length;
  const invested = book.reduce((a, p) => a + (p.weight ?? 0), 0);
  const holdsBook = strat?.engine === 'book' || strat?.engine === 'benchmark';
  const paper = !!strat && strat.isPaper;
  // No warning for a strategy whose paper clock has not started (a paused or not-yet-run paper night).
  const paperWarn = !!run.sessionDate && run.paperStatus !== 'success' && !!strat?.paperStart;
  const StratIcon = strat ? strategyIcon(strat.icon) : Landmark;
  const href = (id: string) => `/positions?s=${encodeURIComponent(id)}`;
  const [noneTitle, noneSub] = emptyState(strat);
  const orderSession = live ? pending.sessionDate : null;
  // Monthly pick, weekly size check (web/lib/cadence.ts): only these strategies show the change per order.
  const splitCadence = !!strat && picksMonthlySizesWeekly(strat.rulesId);
  const held = heldUsd(book);
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
          {strat && (
            // Retired strategies hold nothing and place nothing: only the one asked for by link is kept.
            <StrategySwitch strategies={roster.filter(r => r.status !== 'retired' || r.id === strat.id)} current={strat.id}
              href={href} label="Strategy" />
          )}
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

        {PAPER_PAUSED && <PausedNote />}

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
            {bracket.map((p, i) => <BracketCard key={p.key} q={p} bg={cardBg(p.slot, i)} />)}
            {book.map((p, i) => p.kind === 'benchmark'
              ? <BenchmarkCard key={p.key} q={p} />
              : <BookCard key={p.key} q={p} bg={cardBg(null, bracket.length + i)} />)}
          </div>
        )}

        {strat && live && orderSession && (
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
                {pending.orders.map(o => (
                  <OrderRow key={o.key} o={o} equity={pending.equity} passed={checks.find(v => v.symbol === o.symbol && v.verdict === 'allow')}
                    size={splitCadence && o.kind === 'book' ? orderSizeChange(o.weight, pending.equity, o.symbol, held) : undefined} />
                ))}
              </ul>
            )}
          </section>
        )}

        {/* Q5: where the page used to render nothing at all, it now says which of the five it is. */}
        {strat && asksOrders && !live && (
          <Standing st={strat} state={panel} pipeline={pipeline} when={when} pending={pending} />
        )}

        {strat && panel === 'spent' && pending.sessionDate && pending.orders.length > 0 && (
          <SpentDecision st={strat} session={pending.sessionDate} orders={pending.orders} />
        )}

        {strat && !pending.decision && preview.picks.length > 0 && preview.dataDate && (
          <WouldPick st={strat} preview={preview} />
        )}

        {strat && live && orderSession && sheet && <VetoedTonight st={strat} session={orderSession} sheet={sheet} />}
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
  if (st.engine === 'book' && picksMonthlySizesWeekly(st.rulesId)) {
    return ['In cash.', `${st.short} makes its first decision at its first paper session, then picks its stocks on the first session of each month and checks how much to hold on the first session of each week.`];
  }
  if (st.engine === 'book') return ['In cash.', `${st.short} makes its first decision at its first paper session, then rebalances on the first session of each month.`];
  return ['No open positions.', null];
}

function noOrders(st: Strategy, p: Pending, sheet: VetoSheet | null): string {
  if (st.engine === 'book') {
    if (p.decision) return `No orders. ${st.short} decided to hold cash.`;
    return picksMonthlySizesWeekly(st.rulesId)
      ? `No orders. ${st.short} keeps what it holds. It picks its stocks on the first session of each month and checks how much to hold on the first session of each week.`
      : `No orders. ${st.short} keeps what it holds until it rebalances on the first session of each month.`;
  }
  if (sheet && sheet.state === 'missing') return `No orders. ${st.short} buys nothing this session.`;
  if (sheet && sheet.state === 'failed') return `No orders. ${st.short} sits this session out.`;
  if (sheet && sheet.allowed === 0) return 'No orders. Nothing passed the news check.';
  return 'No setups tonight. Cash is a position.';
}

/**
 * Paper trading is switched off (`PAPER_PAUSED` in `.github/workflows/nightly.yml`). The fifth state
 * of handover Q5, and the one nothing in the app used to say anywhere. While it holds, no paper
 * order is placed and no paper session is stepped, so every panel below stays on the last decision;
 * the nightly's price step still runs, so marks and positions are current.
 */
function PausedNote() {
  return (
    <section className={`sheet over bg-butter ${s.paused}`} role="status">
      <span className={s.pausedIcon} aria-hidden="true"><Pause size={20} /></span>
      <div className={s.pausedText}>
        <span className={s.pausedTitle}>Paper trading is paused</span>
        <span className={s.pausedSub}>
          No paper orders are placed and no paper session is stepped while the roster is rebuilt to
          pay the real broker fees. Prices and positions below are still updated every night.
        </span>
      </div>
    </section>
  );
}

/**
 * Why there is nothing to act on, in plain words (handover Q5), for everything that is not a live
 * decision. The cadence sentence comes from `noOrders()` so the vocabulary lives in one place. The
 * "next run is due" line is suppressed while paper is paused: the next run will not produce a
 * decision, and saying it would is the kind of sentence this panel exists to delete.
 */
function standingWords(
  st: Strategy, state: PanelState, pipeline: PipelineState, when: Timing, p: Pending,
): { title: string; body: string; next: string | null } {
  const dueLine = `The next nightly run is due ${shortDate(wibDate(when.dueAt))} at ${wibTime(when.dueAt)} WIB.`;
  const nextLine = PAPER_PAUSED ? null : dueLine;

  // A retired strategy is finished: it will never decide again, so a "next run is due" line would
  // be false for it even when paper is running. Its last decision is shown as the record it is.
  if (st.status === 'retired') {
    const was = p.sessionDate ? shortDate(p.sessionDate) : 'an earlier session';
    return {
      title: `${st.short} has been replaced`,
      body: p.orders.length > 0
        ? `${st.short} is retired. The ${p.orders.length} ${p.orders.length === 1 ? 'position' : 'positions'} below are what it decided for the ${was} US session before it was replaced — a record of what it decided, never an order to place. Its successor runs in its place.`
        : `${st.short} is retired and decides nothing further. Its successor runs in its place.`,
      next: null,
    };
  }

  if (state === 'never') {
    return {
      title: 'Paper trading has not started',
      body: `${st.short} places its first paper orders at its first paper session. Nothing is pending.`,
      next: nextLine,
    };
  }
  if (pipeline === 'late') {
    return {
      title: 'The nightly run is late',
      body: `A decision for the ${shortDate(when.target)} US session was due at ${wibTime(when.dueAt)} WIB, and the last retry ran at ${wibTime(when.lateAfter)} WIB. Nothing new has arrived.`,
      next: 'Nothing on this page is an instruction to trade.',
    };
  }
  if (state === 'spent') {
    const was = p.sessionDate ? shortDate(p.sessionDate) : 'an earlier session';
    const body = p.orders.length > 0
      ? `${st.short} decided ${p.orders.length} ${p.orders.length === 1 ? 'position' : 'positions'} for the ${was} US session. That session has closed, so they are a record of what it decided — not an order to place.`
      : `${st.short} had nothing to decide for the ${was} US session, and that session has closed.`;
    return { title: 'The last decision has expired', body, next: nextLine };
  }
  // 'holding' — the common state, roughly three weeks in four for a monthly book.
  return {
    title: `Nothing was due for ${p.sessionDate ? shortDate(p.sessionDate) : 'the next session'}`,
    body: noOrders(st, p, null),
    next: nextLine,
  };
}

function Standing({ st, state, pipeline, when, pending }: {
  st: Strategy; state: PanelState; pipeline: PipelineState; when: Timing; pending: Pending;
}) {
  const w = standingWords(st, state, pipeline, when, pending);
  const late = pipeline === 'late';
  return (
    <section className={`sheet over bg-sheet ${s.standing} ${late ? s.standingLate : ''}`} role="status">
      <div className={s.standingHead}>
        <span className={s.standingIcon} aria-hidden="true">
          {late ? <TriangleAlert size={22} /> : <Clock size={22} />}
        </span>
        <span className="eyebrow">{late ? 'Nightly run' : 'Nothing to act on'}</span>
      </div>
      <span className={s.standingTitle}>{w.title}</span>
      <span className={s.standingBody}>{w.body}</span>
      {w.next && <span className={s.standingNext}>{w.next}</span>}
    </section>
  );
}

/**
 * The decision whose session has closed, kept visible rather than removed. Removing it is what
 * caused the incident: on 2026-10-08 the owner read the blank page as data loss while 80
 * `book_targets` rows and four orders sat untouched. Shown as a record and nothing else — rank,
 * ticker, and for a book its target share of the portfolio. Every field that reads like an order
 * ticket (limit, stop, take-profit, share count, dollar size) and every copy button is deliberately
 * absent, so no row here can be mistaken for something to place.
 */
function SpentDecision({ st, session, orders }: { st: Strategy; session: string; orders: PendingOrder[] }) {
  return (
    <section className={`sheet over bg-stone ${s.spent}`}>
      <div className={`${s.between} ${s.spentHead}`}>
        <span className="eyebrow">What {st.short} decided for {shortDate(session)}</span>
        <span className={`chip ${s.spentChip}`} data-tip="That US session has closed: a record, not an order">Expired</span>
      </div>
      <span className={s.spentNote}>
        The {shortDate(session)} US session has closed. This is the record of what {st.short} decided
        that night. Prices, limits and sizes are not shown, because none of it is a live instruction.
      </span>
      <ul className={s.spentList}>
        {orders.map(o => (
          <li key={o.key} className={s.spentRow}>
            <span className={s.rank}>{o.rank}</span>
            <span className={s.spentSym}>{o.symbol}</span>
            <span className={s.spentGap} />
            {o.weight !== null && <span className={`num ${s.spentWeight}`}>{pct(o.weight, 1)}</span>}
          </li>
        ))}
      </ul>
    </section>
  );
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

function BracketCard({ q, bg }: { q: Holding; bg: string }) {
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

function BookCard({ q, bg }: { q: Holding; bg: string }) {
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

/**
 * What a book strategy would hold if it rebalanced tonight (`book_previews`): shown between its monthly
 * decisions so a monthly strategy is never silent. Display only: nothing trades on it. Each row's reason
 * is the facts the ranking read, as stored (no LLM: previews are replaced every night); a row without
 * stored facts shows no toggle rather than a list of "unavailable" lines. A strategy that picks monthly
 * and checks its sizes weekly says so instead of "only trades when it rebalances".
 */
function WouldPick({ st, preview }: { st: Strategy; preview: Preview }) {
  return (
    <section className={`sheet over bg-sheet ${s.orders}`}>
      <div className={s.between}>
        <span className="eyebrow">{st.short} would pick now</span>
        <span className="chip num">{preview.picks.length}</span>
      </div>
      <span className={s.ordersSub}>
        {picksMonthlySizesWeekly(st.rulesId)
          ? <>From the {shortDate(preview.dataDate!)} closes. {st.short} only changes its stocks on the first session of each month, and checks how much to hold on the first session of each week.</>
          : <>From the {shortDate(preview.dataDate!)} closes. {st.short} only trades when it rebalances, on the first session of each month.</>}
      </span>
      <ul className={s.orderList}>
        {preview.picks.map(p => (
          <li key={p.symbol} className={s.order}>
            <div className={s.orderHead}>
              <span className={s.rank} data-tip="Rank in tonight's list">{p.rank}</span>
              <span className={s.orderSym}>{p.symbol}</span>
              <span className={s.orderCo}>last {usd(p.last)}</span>
            </div>
            <OrderCells cells={[['Weight', pct(p.weight, 1)]]} />
            {p.evidence && <WhyToggle text={null} facts={p.evidence} label="Why it's on the list" />}
          </li>
        ))}
      </ul>
    </section>
  );
}

function OrderRow({ o, equity, passed, size }: { o: PendingOrder; equity: number | null; passed?: Veto; size?: SizeChange | null }) {
  const cells: [string, string][] = o.kind === 'bracket'
    ? [
        ['Limit', o.limit === null ? '—' : usd(o.limit)],
        ['Target', o.tp === null ? '—' : usd(o.tp)],
        ['Stop', o.sl === null ? '—' : usd(o.sl)],
        ['Shares', o.shares === null ? '—' : String(o.shares)],
      ]
    : [
        ['Weight', o.weight === null ? '—' : pct(o.weight, 1)],
        // What the weight buys at tonight's equity; the open's equity sizes the real order.
        ['About', o.weight === null || equity === null ? '—' : usd(o.weight * equity)],
        ['Limit', o.limit === null ? 'Open' : usd(o.limit)],
        o.sl === null && o.tp === null
          ? ['Exit', 'Monthly']
          : ['Stop', o.sl === null ? '—' : usd(o.sl)],
      ];
  return (
    <li className={s.order}>
      <div className={s.orderHead}>
        {o.kind === 'book' && <span className={s.rank}>{o.rank}</span>}
        <span className={s.orderSym}>{o.symbol}</span>
        <span className={s.orderCo}>{companyName(o.company, o.symbol) ? `${o.company} · ` : ''}last {usd(o.last)}</span>
      </div>
      <OrderCells cells={cells} />
      {size !== undefined && <SizeCell size={size} />}
      <WhyToggle text={o.explanation} facts={o.evidence} />
      {passed && (
        <>
          <span className={s.vetoFacts}>{headlinesLabel(passed.headlineCount)} read{passed.earningsDate ? ` · earnings ${monthDay(passed.earningsDate)}` : ''}</span>
          <WhyToggle text={passed.reason.trim() === '' ? null : passed.reason} label="Why it passed the news check"
            missing="No reason was stored for this check." />
        </>
      )}
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

/**
 * Split-cadence strategies only: the order against what is held now, at tonight's marks and equity.
 * "No change" when the gap is under 1% of paper equity, the engine's RESIZE_BAND (web/lib/cadence.ts).
 */
function SizeCell({ size }: { size: SizeChange | null }) {
  return (
    <dl className={s.cells}>
      <div className={`${s.cell} ${s.cellWide}`} data-tip={size ? sizeTip(size) : 'Paper equity is not known yet'}>
        <dt>Against what it holds now</dt>
        <dd className="num">{size ? sizeLabel(size) : '—'}</dd>
      </div>
    </dl>
  );
}

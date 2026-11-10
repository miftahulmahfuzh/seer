import type { CSSProperties } from 'react';
import Link from 'next/link';
import { Archive, Check, CircleDashed, Crown, X } from 'lucide-react';
import { currentUser } from '@/auth';
import { AppHeader } from '@/components/AppHeader';
import { displayIcons, strategyIcon } from '@/components/roster';
import { PaperChip } from '@/components/PaperChip';
import { StrategySwitch } from '@/components/StrategySwitch';
import { leaderboard, monthly, runStatus, type Board } from '@/lib/data';
import { monthDay, monthName, shortDate, signedPct } from '@/lib/format';
import { checklist } from '@/lib/metrics';
import { isSeraUser } from '@/lib/sera/access';
import { methodHref } from '@/lib/sera/paper';
import { wibDate } from '@/lib/session';
import { PickName } from './PickName';
import { RetiredShelf } from './RetiredShelf';
import {
  BENCHMARK_DASH, compare, LOOK_FALLBACK, looks, MIN_COMMON_SESSIONS, monthLines, NO_GATE, pickResearch,
  researchOf, retiredLabel, scoreOf, sinceStartLine, spyOverSpan, stacks, twinChipTip, windowLine,
  type CompareRow, type Look, type MonthLine,
} from './view';
import s from './leaderboard.module.css';

export const dynamic = 'force-dynamic';

const W = 340, H = 170;

type Search = { s?: string };

export default async function Leaderboard({ searchParams }: { searchParams: Promise<Search> }) {
  const now = new Date();
  const q = await searchParams;
  const [stored, run, user] = await Promise.all([leaderboard(), runStatus(now), currentUser()]);
  // R1: every card and switch button draws its own icon. A Claude twin's row stores its original's
  // icon (the engine copies it), so the unique one is resolved here from the whole board, once, and
  // everything below keeps reading `st.icon`.
  const icons = displayIcons(stored.rows.map(r => r.strategy));
  const board: Board = {
    ...stored,
    rows: stored.rows.map(r => ({ ...r, strategy: { ...r.strategy, icon: icons.get(r.strategy.id) ?? r.strategy.icon } })),
  };

  // The live strategies hold the board -- chart, legend, switch and the row of cards. A retired one
  // that traded keeps its card and its record on the folded shelf under them (`RetiredShelf`).
  const live = board.rows.filter(r => r.strategy.status !== 'retired');
  const retiredRows = board.rows.filter(r => r.strategy.status === 'retired');
  const roster = board.rows.map(r => r.strategy);
  const lookMap = looks(roster);
  const lookOf = (id: string): Look => lookMap.get(id) ?? LOOK_FALLBACK;
  const shortOf = new Map(roster.map(st => [st.id, st.short]));
  const research = researchOf(roster);
  const champ = board.rows.find(r => r.strategy.isChampion);
  const spy = board.rows.find(r => r.strategy.isBenchmark);
  const spyRet = spy?.metrics.totalReturn ?? null;

  // R3: rank over the sessions the compared strategies actually share, never over raw total return
  // across unequal paper starts (invariant 6). `wline` is what puts that window on the page, and
  // `cmpOf` is what lets a card say "not ranked" instead of silently dropping out of the order.
  const cmp = compare(board.rows);
  const best = cmp.best;
  const wline = windowLine(cmp);
  const cmpMap = new Map(cmp.rows.map(r => [r.strategy.id, r]));
  const cmpOf = (id: string): CompareRow | null => cmpMap.get(id) ?? null;

  // Research only: SPY is in every month row's SPY column, so it is not selectable here. Retired
  // strategies stay selectable (their record is the point) but are never the default.
  const pick = pickResearch(research, q.s);
  const pickRow = pick ? board.rows.find(r => r.strategy.id === pick.id) : undefined;
  // The chart, the legend and the switch show the live strategies, plus a retired one only while it
  // is the pick: its line and its switch button are then the context for the sheets it fills.
  const shown = pickRow && pickRow.strategy.status === 'retired' ? [...live, pickRow] : live;
  const switchable = researchOf(shown.map(r => r.strategy));
  const gate = pickRow?.strategy.gate ?? null;
  // "Beats SPY" measures the benchmark over the picked strategy's own span, not over SPY's whole
  // record: the two need not have started on the same day once the roster is promotable.
  const pickSpy = pickRow && spy ? spyOverSpan(spy.curve, pickRow.curve) : null;
  const items = pickRow && gate ? checklist(pickRow.metrics, pickSpy, gate) : [];
  const score = scoreOf(items, gate ?? NO_GATE);
  // The latest month is partial while the engine's next session (runStatus().sessionDate) is in it.
  const table = pick ? await monthly(pick.id, run.sessionDate) : null;
  // The picked strategy's name doubles as the way into Sera's method page — but only for the one
  // account /sera lets in. For anyone else `requireSera` is a 404, and the nav already hides the
  // section from them: a link here would dead-end and announce what the nav is keeping quiet.
  // A Claude twin runs its original's method with Claude's objections taken out, so its name
  // opens the original's method page; the twin has no lab method of its own.
  const seeMethod = pick && isSeraUser(user?.email) ? methodHref(pick.twinOf ?? pick.id) : null;
  const since = table ? sinceStartLine(table) : null;
  const months = table ? monthLines(table) : [];

  // Forward test runs from the earliest paper snapshot; strategies promoted later start later, so
  // this is the board's whole span and NOT the window anything is ranked over (see `wline`).
  const period = board.from && board.to ? `${monthDay(board.from)} – ${monthDay(board.to)}` : 'Not started';
  const chart = buildChart({ ...board, rows: shown }, lookOf);
  const ret = (v: number | null) => (v === null ? '—' : signedPct(v, 1));
  const tone = (v: number | null) => (v === null ? '' : v < 0 ? 'neg' : 'pos');
  const champRet = champ?.metrics.totalReturn ?? null;

  // Big figure = the champion (SPY today, D2). Second figure = the best research strategy over the
  // common window while the champion is the benchmark; otherwise SPY, as in the design. With no
  // common window there is no "best": a number here without a window would be the very claim R3
  // exists to stop making.
  const second = champ?.strategy.isBenchmark
    ? {
        value: best ? ret(best.totalReturn) : '—',
        mobile: best ? `Best · ${best.strategy.short}` : 'Not ranked',
        // With nothing ranked, the window row right under the headline already says "No common
        // window yet" and how far off one is; repeating it here printed it twice on desktop.
        desk: best ? `${best.strategy.name}, best over the common window` : 'Not ranked',
      }
    : { value: ret(spyRet), mobile: 'SPY', desk: 'SPY' };

  const chartSheet = (
    <section className={`sheet bg-sheet ${s.chartSheet}`}>
      <div className={`${s.between} ${s.pad} mobile-only`}>
        <span className="eyebrow">Forward test</span>
        <span className="pill-outline">{period}</span>
      </div>
      <div className={`${s.headline} ${s.pad}`}>
        <div className={s.stats}>
          <div className={s.stat}>
            <span className={`num ${s.big} ${tone(champRet)}`}>{ret(champRet)}</span>
            <span className={s.statLabel}>
              <Crown size={14} />
              <span>{champ?.strategy.name ?? 'No champion'}<span className="desk-only">, champion</span></span>
            </span>
          </div>
          <div className={s.stat}>
            <span className={`num ${s.mid}`}>{second.value}</span>
            <span className={s.statLabel}>
              <span className="mobile-only">{second.mobile}</span>
              <span className="desk-only">{second.desk}</span>
            </span>
          </div>
          <div className={`${s.stat} mobile-only`}>
            <span className={`num ${s.mid}`}>{champ?.curve.length ?? 0}</span>
            <span className={s.statLabel}>Sessions</span>
          </div>
        </div>
        <Legend rows={shown} lookOf={lookOf} className="desk-only" />
      </div>
      <div className={`${s.window} ${s.pad}`}>
        <span className={s.windowLabel}>{wline.label}</span>
        <span className={s.windowDetail}>{wline.detail}</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className={s.chart} role="img"
        aria-label="Equity curves of each strategy against SPY">
        {chart.grid.map((y, i) => <line key={i} x1="0" x2={W} y1={y} y2={y} vectorEffect="non-scaling-stroke" stroke="var(--hair)" />)}
        <line x1="0" x2={W} y1={chart.zero} y2={chart.zero} vectorEffect="non-scaling-stroke" stroke="var(--outline)" strokeDasharray="3 3" />
        {chart.lines.map(l => (
          <path key={l.id} d={l.d} vectorEffect="non-scaling-stroke" fill="none" stroke={l.color} strokeWidth={l.width}
            strokeDasharray={l.dash ?? undefined} strokeLinecap="round" strokeLinejoin="round" />
        ))}
      </svg>
      <div className={`${s.axis} ${s.pad}`}>{chart.labels.map((l, i) => <span key={i}>{l}</span>)}</div>
      <Legend rows={shown} lookOf={lookOf} className={`${s.pad} ${s.legendRow} mobile-only`} />
    </section>
  );

  const checklistSheet = (
    // Butter on mobile (the design's checklist sheet); on desktop it takes the picked strategy's tint.
    <section className={`sheet over ${s.check}`} style={{ '--pick': pick ? lookOf(pick.id).tint : undefined } as CSSProperties}>
      {pick && switchable.length > 1 && (
        <div className={s.switch}>
          <StrategySwitch strategies={switchable} current={pick.id}
            href={id => `/leaderboard?s=${encodeURIComponent(id)}`} label="Strategy" fit />
        </div>
      )}
      <span className="eyebrow">Go-live checklist · <PickName name={pick?.name} href={seeMethod} /></span>
      <div className={s.score}>
        <span className={`num ${s.scoreNum}`}>{score.passed}/{score.total}</span>
        <span className={s.scoreText}>{score.lines[0]}<br />{score.lines[1]}</span>
      </div>
      {items.map(c => (
        <div key={c.label} className={s.item}>
          {c.ok
            ? <span className={s.ok} role="img" aria-label="Passed"><Check size={18} strokeWidth={2.25} /></span>
            : <span className={s.no} role="img" aria-label="Not yet"><X size={18} strokeWidth={2.25} /></span>}
          <span className={s.itemLabel}>{c.label}</span>
          <span className={`chip num ${s.itemVal}`}>{c.val}</span>
        </div>
      ))}
    </section>
  );

  // Desktop: the live row is one deck per family (`stacks`), an original with its Claude twin
  // tucked behind it. The picked card drops into this sheet as a tab, and at either end of the row
  // the tab meets the sheet's own rounded corner, which has to square off for the two to read as
  // one surface. The row's leftmost card is always the first deck's top card. The deck holding the
  // pick is always open (its cards side by side), so when the pick sits in the last deck,
  // `decks.flat().at(-1)` is the rightmost card on screen.
  const decks = stacks(live);
  const ids = decks.flat().map(r => r.strategy.id);
  const tabEdge = !pick ? undefined : ids[0] === pick.id ? 'first' : ids.at(-1) === pick.id ? 'last' : undefined;
  // A deck is open when it holds the pick, so "open" can never be stored apart from the pick.
  const isOpen = (rows: Board['rows']) => rows.some(r => r.strategy.id === pick?.id);
  // The retired shelf keeps the live row's column width (`RetiredShelf`'s `cols`). The row is no
  // longer one column per card: it is one per deck, and the open deck spans one per card.
  const rowCols = decks.reduce((n, d) => n + (isOpen(d) ? d.length : 1), 0);
  const monthsSheet = (
    <section className={`sheet over ${pick ? lookOf(pick.id).bg : 'bg-sheet'} ${s.months}`} data-tab={tabEdge}
      aria-labelledby="months-title">
      <h2 id="months-title" className="eyebrow">Month by month · <PickName name={pick?.name} href={seeMethod} /></h2>
      {pick && since ? (
        <table className={s.table}>
          <thead>
            <tr>
              <th scope="col">Month</th>
              <th scope="col">Return</th>
              <th scope="col">SPY</th>
              <th scope="col">Trades</th>
              <th scope="col">Worst drop</th>
            </tr>
          </thead>
          <tbody>
            <MonthRow line={since} total />
            {months.map(m => <MonthRow key={m.key} line={m} />)}
          </tbody>
        </table>
      ) : (
        <div className={s.none}>{pick ? 'No paper sessions yet.' : 'No paper strategy on the roster.'}</div>
      )}
      <div className={s.key}>
        <span><CircleDashed size={15} />Partial month</span>
        <span>One month is mostly luck</span>
      </div>
    </section>
  );

  return (
    <>
      <AppHeader date={shortDate(wibDate(now))} title="Leaderboard" demo={run.isDemo}
        deskAside={<span className="pill-outline" style={{ height: 52, fontSize: 16, color: 'var(--ink)' }}>Forward test · {period}</span>} />
      <div className="stack">
        <div className={s.top}>{chartSheet}{checklistSheet}</div>
        {monthsSheet}
        <div className={s.cards}>{decks.map(d => deck(d))}</div>
        {retiredRows.length > 0 && (
          <RetiredShelf count={retiredRows.length} cols={rowCols} open={pick?.status === 'retired'}>
            {retiredRows.map(r => card(r, false))}
          </RetiredShelf>
        )}
        <div className="nav-clear" />
      </div>
    </>
  );

  /**
   * One family on the desktop row: the original on top, its Claude twin tucked behind it with its
   * edge and colour peeking out above and to the right. The deck holding the pick is open. It takes
   * one column per card, fans the twin out beside the original and pops forward in its own slot,
   * so every other deck keeps its place. "Open" is derived from the pick and never stored, so a deck
   * cannot be open without holding it. Below 1024px the deck is `display: contents` and its cards
   * fall back into the mobile column exactly as before. CSS alone moves the cards: the deck and
   * card keys are stable ids, so React keeps the same elements across a pick and their transform
   * transitions run with no client component.
   */
  function deck(rows: Board['rows']) {
    const open = isOpen(rows);
    return (
      <div key={rows[0].strategy.id} className={s.deck} data-deck={rows[0].strategy.id}
        data-open={open ? '' : undefined} style={{ '--n': rows.length } as CSSProperties}>
        {rows.map((r, depth) => card(r, true, { depth, open }))}
      </div>
    );
  }

  /**
   * One strategy's card. `tab`: the picked live card becomes the tab into the month-by-month sheet
   * right under the live row (desktop); a retired card sits on the shelf below that sheet, so when
   * it is the pick it is marked as picked instead of pretending to be attached to it.
   * `place`: a live card's position in its deck. A twin behind a closed deck shows only its edge on
   * desktop, so it carries its name as its accessible name, and as the tooltip of the edge.
   */
  function card({ strategy: st, metrics: m }: Board['rows'][number], tab: boolean, place?: { depth: number; open: boolean }) {
    const Icon = strategyIcon(st.icon); // st.icon is already the unique display icon (`board` above).
    const look = lookOf(st.id);
    const dash = (v: string) => (st.isBenchmark ? '—' : v);
    const cr = cmpOf(st.id);
    const retired = st.status === 'retired';
    const active = st.id === pick?.id;
    const tucked = place !== undefined && place.depth > 0 && !place.open;
    // Desktop shows the code; the full name and the one-line description live in this tip.
    const tip = `${st.name}\n${st.sub}`;
    const body = (
      <>
        {/* Desktop, a tucked twin: the strip that peeks out from behind the deck is its whole
            clickable face, so the strip carries the name. Never rendered on an open deck. */}
        {tucked && <span className={s.peek} data-tip={st.name} aria-hidden="true" />}
        <div className={s.cardHead}>
          <div className={s.cardName}>
            <div className={s.titleRow}>
              {/* Mobile: one row, the name gives way (ellipsis) before the chips wrap under it.
                  Desktop: the whole code (a twin's breaks after its '+'), with the chips on their
                  own line below. */}
              <span className={s.name} data-tip={tip}>
                <span className={`${s.nameText} mobile-only`}>{st.name}</span>
                <span className={`${s.nameText} desk-only`}>{breakable(st.short)}</span>
                {st.isChampion && <span data-tip="Champion" aria-label="Champion" role="img" className={`${s.crown} mobile-only`}><Crown size={20} /></span>}
              </span>
              {/* Desktop: the status line under the code — champion, Claude twin (Paper), retired, not ranked. */}
              <span className={s.chips}>
                {st.isChampion && <span data-tip="Champion" aria-label="Champion" role="img" className={`${s.crown} desk-only`}><Crown size={20} /></span>}
                {st.twinOf !== null && <PaperChip size="sm" tip={twinChipTip(shortOf.get(st.twinOf) ?? null)} />}
                {retired && (
                  <span className={`chip ${s.retired}`}
                    data-tip="Retired: it stopped trading and keeps its whole record">
                    <Archive size={14} strokeWidth={1.75} aria-hidden="true" />
                    {retiredLabel(st.paperEnd)}
                  </span>
                )}
                {cr?.status === 'insufficient' && (
                  <span className={`chip ${s.unranked}`}
                    data-tip={`Not ranked: fewer than ${MIN_COMMON_SESSIONS} sessions shared with the others`}>
                    Not ranked
                  </span>
                )}
              </span>
            </div>
            <span className={s.cardSub}>{st.sub}</span>
          </div>
          <span className={s.icon} data-tip={tip}><Icon size={22} strokeWidth={1.6} /></span>
        </div>
        <div className={s.metrics}>
          <div className={s.metric}><span className={`num ${s.ret} ${tone(m.totalReturn)}`}>{ret(m.totalReturn)}</span><span className={s.mLabel}><span className="mobile-only">Return</span><span className="desk-only">Total return</span></span></div>
          <div className={s.metric}><span className="num">{dash(m.winRate === null ? '—' : Math.round(m.winRate * 100) + '%')}</span><span className={s.mLabel}>Win rate</span></div>
          <div className={s.metric}><span className="num">{dash(m.profitFactor === null ? '—' : m.profitFactor === Infinity ? '∞' : m.profitFactor.toFixed(2))}</span><span className={s.mLabel}><span className="mobile-only">Profit f.</span><span className="desk-only">Profit factor</span></span></div>
          <div className={s.metric}><span className="num">{m.maxDrawdown === null ? '—' : (m.maxDrawdown * 100).toFixed(1) + '%'}</span><span className={s.mLabel}><span className="mobile-only">Max DD</span><span className="desk-only">Max drawdown</span></span></div>
          <div className={s.metric}><span className="num">{dash(String(m.trades))}</span><span className={s.mLabel}>Trades</span></div>
        </div>
      </>
    );
    const picked = active ? ` ${tab ? s.cardActive : s.cardPicked}` : '';
    const cls = `sheet ${tab ? 'over ' : ''}${look.bg} ${s.card}${picked}`;
    const style = { '--tint': look.tint, ...(place && { '--depth': place.depth }) } as CSSProperties;
    // Which end of the row the tab sits at, if any: there the sheet's corner squares off instead
    // of the tab drawing a fillet past the row's edge.
    const edge = active && tab ? tabEdge : undefined;
    // SPY is in every month row already, so only research cards pick the month-by-month sheet.
    return st.isBenchmark ? (
      <article key={st.id} data-status={cr?.status ?? 'benchmark'} className={cls} style={style}>{body}</article>
    ) : (
      <Link key={st.id} href={`/leaderboard?s=${encodeURIComponent(st.id)}`} scroll={false}
        data-status={cr?.status ?? 'benchmark'} data-edge={edge} aria-current={active ? 'true' : undefined}
        aria-label={tucked ? st.name : undefined}
        className={`${cls} ${s.cardLink}`} style={style}>{body}</Link>
    );
  }
}

/** A twin's code may break after its '+' ('RAW35+' / 'Claude') rather than mid-word in a narrow card. */
function breakable(code: string) {
  const at = code.indexOf('+');
  return at < 0 ? code : <>{code.slice(0, at + 1)}<wbr />{code.slice(at + 1)}</>;
}

function MonthRow({ line, total }: { line: MonthLine; total?: boolean }) {
  return (
    <tr className={total ? s.total : undefined}>
      <th scope="row">
        <span className={s.monthLabel}>
          {line.label}
          {line.partial && (
            <span className={s.partial} role="img" aria-label="Partial month" data-tip="Partial month">
              <CircleDashed size={14} />
            </span>
          )}
        </span>
      </th>
      <td className={`num ${line.ret.tone}`}>{line.ret.text}</td>
      <td className="num">{line.spy}</td>
      <td className="num">{line.trades}</td>
      <td className="num">{line.drop}</td>
    </tr>
  );
}

/**
 * One swatch + short label per strategy (full name as its tooltip). On desktop it is one row: it
 * sits beside the headline figures when it fits and drops under them when it does not. Past about
 * a dozen strategies its codes ellipsise rather than wrap (`.legendLabel`). On mobile it is the
 * wrapping row under the axis.
 */
function Legend({ rows, lookOf, className }: {
  rows: Board['rows']; lookOf: (id: string) => Look; className: string;
}) {
  return (
    <div className={`${s.legend} ${className}`}>
      {rows.map(({ strategy: st }) => {
        const look = lookOf(st.id);
        const retired = st.status === 'retired';
        const tip = retired ? `${st.name} · ${retiredLabel(st.paperEnd).toLowerCase()}` : st.name;
        return (
          <span key={st.id} data-tip={tip} aria-label={tip}
            className={retired ? `${s.legendItem} ${s.legendRetired}` : s.legendItem}>
            {look.dash
              ? <span className={s.swatchDash} style={{ borderTopColor: look.line, borderTopStyle: look.dash === BENCHMARK_DASH ? 'dotted' : 'dashed' }} />
              : <span className={s.swatch} style={{ background: look.line }} />}
            <span className={s.legendLabel}>{st.short}</span>
          </span>
        );
      })}
    </div>
  );
}

function buildChart(board: Board, lookOf: (id: string) => Look) {
  const dates = [...new Set(board.rows.flatMap(r => r.curve.map(c => c.date)))].sort();
  const xi = new Map(dates.map((d, i) => [d, i]));
  const series = board.rows.filter(r => r.curve.length > 1).map(r => ({
    row: r,
    pts: r.curve.map(c => ({ x: xi.get(c.date)!, v: (c.equity / r.curve[0].equity - 1) * 100 })),
  }));
  const all = series.flatMap(sr => sr.pts.map(p => p.v)).concat(0);
  const lo = Math.min(...all), hi = Math.max(...all);
  const span = hi - lo || 1;
  const y = (v: number) => +(H - 10 - ((v - lo) / span) * (H - 24)).toFixed(1);
  const x = (i: number) => +((i / Math.max(1, dates.length - 1)) * W).toFixed(1);

  // Champion last so it draws on top.
  const ordered = [...series].sort((a, b) => Number(a.row.strategy.isChampion) - Number(b.row.strategy.isChampion));
  const lines = ordered.map(({ row, pts }) => {
    const look = lookOf(row.strategy.id);
    return {
      id: row.strategy.id,
      d: pts.map((p, i) => `${i ? 'L' : 'M'}${x(p.x)} ${y(p.v)}`).join(' '),
      color: look.line,
      width: look.width,
      dash: look.dash,
    };
  });

  const labels: string[] = [];
  if (dates.length) {
    labels.push(monthDay(dates[0]));
    const first = monthName(dates[0]), last = monthName(dates[dates.length - 1]);
    for (const m of [...new Set(dates.map(monthName))]) if (m !== first && m !== last) labels.push(m);
    if (dates.length > 1) labels.push(monthDay(dates[dates.length - 1]));
  }
  return { lines, labels, zero: y(0), grid: [y(hi), y((hi + lo) / 2)] };
}

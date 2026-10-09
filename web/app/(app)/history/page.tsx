import {
  ArrowDownToLine, ArrowRightLeft, ArrowUpFromLine, CircleDashed, CircleSlash, Hourglass, List, OctagonX,
  SkipForward, Target, TrendingDown, TrendingUp,
  type LucideIcon,
} from 'lucide-react';
import Link from 'next/link';
import type { CSSProperties } from 'react';
import { AppHeader } from '@/components/AppHeader';
import { PaperChip } from '@/components/PaperChip';
import { sharesLabel, strategyIcon } from '@/components/roster';
import { ALL, StrategySwitch } from '@/components/StrategySwitch';
import { closedTrades, fills, runStatus, strategies } from '@/lib/data';
import { monthDay, money, shortDate, signedPct, signedUsd, usd } from '@/lib/format';
import { emptyNote, fillVerb, historyHref } from '@/lib/history';
import { wibDate } from '@/lib/session';
import s from './history.module.css';

export const dynamic = 'force-dynamic';

// [icon, tooltip, legend label]
const REASON: Record<string, [LucideIcon, string, string]> = {
  tp: [Target, 'Take profit hit', 'Target'],
  sl: [OctagonX, 'Stop loss hit', 'Stop'],
  time: [Hourglass, 'Time exit, day 5', 'Day 5'],
  gap: [SkipForward, 'Gapped past stop at open', 'Gap'],
  signal: [ArrowRightLeft, 'Rules said sell, sold at the open', 'Signal'],
  forced: [CircleSlash, 'Forced close, no more prices', 'Forced'],
};
const UNKNOWN_REASON: [LucideIcon, string, string] = [CircleDashed, 'Closed', 'Closed'];
const OUT_BTNS: [string, LucideIcon, string][] = [['all', List, 'Wins and losses'], ['win', TrendingUp, 'Wins only'], ['loss', TrendingDown, 'Losses only']];
const SIDE_BTNS: [string, LucideIcon, string][] = [['all', List, 'Buys and sells'], ['buy', ArrowDownToLine, 'Buys only'], ['sell', ArrowUpFromLine, 'Sells only']];

/** The two things "history" can mean. `trades` is what closed; `activity` is what the engine did. */
const VIEWS = [['trades', 'Trades'], ['activity', 'Activity']] as const;
type View = (typeof VIEWS)[number][0];

type Search = { s?: string; o?: string; v?: string };

export default async function History({ searchParams }: { searchParams: Promise<Search> }) {
  const now = new Date();
  const q = await searchParams;
  const roster = await strategies();
  const research = roster.filter(r => !r.isBenchmark);
  const strat = q.s && research.some(r => r.id === q.s) ? q.s : ALL;
  const view: View = q.v === 'activity' ? 'activity' : 'trades';
  // One query param for both filter groups: they never share a view, and `o=buy` reading as
  // `outcome=all` in the Trades view is exactly the fallback already written for a junk value.
  const outcome = view === 'trades' && (q.o === 'win' || q.o === 'loss') ? q.o : 'all';
  const side = view === 'activity' && (q.o === 'buy' || q.o === 'sell') ? q.o : 'all';
  const only = strat === ALL ? null : strat;
  const [run, rows, acts] = await Promise.all([
    runStatus(now),
    view === 'trades' ? closedTrades(only, outcome === 'all' ? null : outcome) : Promise.resolve([]),
    view === 'activity' ? fills(only, side === 'all' ? null : side) : Promise.resolve([]),
  ]);
  const byId = new Map(roster.map(r => [r.id, r]));
  const net = rows.reduce((a, r) => a + r.pnl, 0);
  const wins = rows.filter(r => r.pnl > 0).length;
  // Cash out and cash in, fees included (book_fills.cash_usd is signed and net of the fee).
  const bought = acts.reduce((a, f) => a + (f.side === 'buy' ? -f.cash : 0), 0);
  const sold = acts.reduce((a, f) => a + (f.side === 'sell' ? f.cash : 0), 0);
  const feesKnown = acts.some(f => f.fee !== null);
  const fees = acts.reduce((a, f) => a + (f.fee ?? 0), 0);

  const empty = emptyNote({ what: view, strategy: strat === ALL ? null : byId.get(strat) ?? null, outcome });
  const sideBtns = view === 'trades' ? OUT_BTNS : SIDE_BTNS;
  const sideOn = view === 'trades' ? outcome : side;

  const href = (next: Search) => historyHref({ s: strat, o: sideOn, v: view }, next);

  return (
    <>
      <AppHeader date={shortDate(wibDate(now))} title="History" demo={run.isDemo} />
      <div className="stack">
        <section className={`sheet bg-sheet ${s.summary}`}>
          <nav className={s.tabs} aria-label="History view">
            {VIEWS.map(([v, label]) => (
              <Link key={v} href={href({ v })} replace scroll={false} className={s.tab}
                aria-current={view === v ? 'true' : undefined}>{label}</Link>
            ))}
          </nav>
          {/* --n: buttons across both pills, so every button shares one size and the row never wraps. */}
          <div className={s.filters} style={{ '--n': research.length + 1 + sideBtns.length } as CSSProperties}>
            <StrategySwitch strategies={research} current={strat} href={id => href({ s: id })}
              label="Strategy filter" allTip="All strategies" seg />
            <div className="seg" role="group" aria-label={view === 'trades' ? 'Outcome filter' : 'Side filter'}>
              {sideBtns.map(([v, Icon, tip]) => (
                <Link key={v} href={href({ o: v })} replace scroll={false} className="icon-btn"
                  data-tip={tip} aria-label={tip} aria-current={sideOn === v ? 'true' : undefined}>
                  <Icon size={19} strokeWidth={sideOn === v ? 2 : 1.5} />
                </Link>
              ))}
            </div>
          </div>
          {view === 'trades' ? (
            <div className={s.stats}>
              <div className={s.stat}><span className={`num ${s.big} ${net < 0 ? 'neg' : 'pos'}`}>{signedUsd(net)}</span><span className={s.sub}>Net result</span></div>
              <div className={s.stat}><span className={`num ${s.mid}`}>{wins}</span><span className={s.sub}>Won</span></div>
              <div className={s.stat}><span className={`num ${s.mid}`}>{rows.length - wins}</span><span className={s.sub}>Lost</span></div>
            </div>
          ) : (
            <div className={s.stats}>
              <div className={s.stat}><span className={`num ${s.big}`}>{usd(bought)}</span><span className={s.sub}>Bought</span></div>
              <div className={s.stat}><span className={`num ${s.mid}`}>{usd(sold)}</span><span className={s.sub}>Sold</span></div>
              <div className={s.stat}><span className={`num ${s.mid}`}>{feesKnown ? usd(fees) : '—'}</span><span className={s.sub}>Fees</span></div>
            </div>
          )}
          {view === 'trades' ? (
            <div className={s.key}>
              {Object.entries(REASON).map(([k, [Icon, tip, label]]) => (
                <span key={k} data-tip={tip}><Icon size={15} />{label}</span>
              ))}
            </div>
          ) : (
            <p className={s.note}>
              Every buy and sell, newest first. The cash is what left or reached the account, fee
              included; a dash means that engine records no fee per fill.
            </p>
          )}
        </section>

        <section className={`sheet over bg-stone ${s.list}`}>
          {(view === 'trades' ? rows.length : acts.length) === 0 && (
            <div className={s.none}>
              <span className={s.noneTitle}>{empty.title}</span>
              <span>{empty.sub}</span>
            </div>
          )}
          {view === 'trades' && rows.map(r => {
            const [RIcon, rTip] = REASON[r.reason] ?? UNKNOWN_REASON;
            const st = byId.get(r.strategyId);
            const SIcon = strategyIcon(st?.icon ?? '');
            const win = r.pnl > 0;
            return (
              <div key={r.key} className={s.row}>
                <span className={s.reason} data-tip={rTip} aria-label={rTip}><RIcon size={19} strokeWidth={1.6} /></span>
                <div className={s.main}>
                  <span className={s.line1}>
                    <span className={s.sym}>{r.symbol}</span>
                    <span className={s.tag} data-tip={st?.name ?? r.strategyId}><SIcon size={12} />{r.strategyShort}</span>
                    {(!st || st.isPaper) && <PaperChip size="sm" />}
                  </span>
                  <span className={`num ${s.line2}`}>{money(r.entry)} → {money(r.exit)} · {monthDay(r.exitDate)}</span>
                </div>
                <div className={`${s.result} ${win ? 'pos' : 'neg'}`}>
                  <span className={`num ${s.pct}`}>{signedPct(r.exit / r.entry - 1)}</span>
                  <span className="num">{signedUsd(r.pnl)}</span>
                </div>
              </div>
            );
          })}
          {view === 'activity' && acts.map(f => {
            const st = byId.get(f.strategyId);
            const SIcon = strategyIcon(st?.icon ?? '');
            const buy = f.side === 'buy';
            const verb = fillVerb(f.side, f.reason);
            return (
              <div key={f.key} className={s.row}>
                <span className={s.reason} data-tip={verb} aria-label={verb}>
                  {buy ? <ArrowDownToLine size={19} strokeWidth={1.6} /> : <ArrowUpFromLine size={19} strokeWidth={1.6} />}
                </span>
                <div className={s.main}>
                  <span className={s.line1}>
                    <span className={s.sym}>{f.symbol}</span>
                    <span className={s.tag} data-tip={st?.name ?? f.strategyId}><SIcon size={12} />{f.strategyShort}</span>
                    {(!st || st.isPaper) && <PaperChip size="sm" />}
                  </span>
                  <span className={`num ${s.line2}`}>{verb} {sharesLabel(f.shares)} at {money(f.price)} · {monthDay(f.date)}</span>
                </div>
                <div className={s.result}>
                  <span className={`num ${s.pct} ${buy ? '' : 'pos'}`}>{buy ? `−${usd(-f.cash)}` : signedUsd(f.cash)}</span>
                  <span className="num">{f.fee === null ? '—' : `fee ${usd(f.fee)}`}</span>
                </div>
              </div>
            );
          })}
        </section>
      </div>
    </>
  );
}

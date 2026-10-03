import {
  BrainCircuit, Gavel, Hourglass, List, ListFilter, OctagonX, Sigma, SkipForward, Target, TrendingDown, TrendingUp,
  type LucideIcon,
} from 'lucide-react';
import Link from 'next/link';
import { AppHeader } from '@/components/AppHeader';
import { closedTrades, runStatus } from '@/lib/data';
import { monthDay, money, shortDate, signedPct, signedUsd } from '@/lib/format';
import { wibDate } from '@/lib/session';
import s from './history.module.css';

export const dynamic = 'force-dynamic';

const STRAT: Record<string, [LucideIcon, string]> = { A: [Sigma, 'Strategy A · Quant'], B: [BrainCircuit, 'Strategy B · ML'], C: [Gavel, 'Strategy C · LLM-veto'] };
const REASON: Record<string, [LucideIcon, string]> = {
  tp: [Target, 'Take profit hit'], sl: [OctagonX, 'Stop loss hit'], time: [Hourglass, 'Time exit, day 5'], gap: [SkipForward, 'Gapped past stop at open'],
};
const STRAT_BTNS: [string, LucideIcon, string][] = [['all', ListFilter, 'All strategies'], ['A', Sigma, 'Strategy A only'], ['B', BrainCircuit, 'Strategy B only'], ['C', Gavel, 'Strategy C only']];
const OUT_BTNS: [string, LucideIcon, string][] = [['all', List, 'Wins and losses'], ['win', TrendingUp, 'Wins only'], ['loss', TrendingDown, 'Losses only']];

type Search = { s?: string; o?: string };

export default async function History({ searchParams }: { searchParams: Promise<Search> }) {
  const now = new Date();
  const q = await searchParams;
  const strat = q.s && q.s in STRAT ? q.s : 'all';
  const outcome = q.o === 'win' || q.o === 'loss' ? q.o : 'all';
  const [run, rows] = await Promise.all([
    runStatus(now),
    closedTrades(strat === 'all' ? null : strat, outcome === 'all' ? null : outcome),
  ]);
  const net = rows.reduce((a, r) => a + r.pnl, 0);
  const wins = rows.filter(r => r.pnl > 0).length;

  const href = (next: Search) => {
    const p = new URLSearchParams();
    const sv = next.s ?? strat, ov = next.o ?? outcome;
    if (sv !== 'all') p.set('s', sv);
    if (ov !== 'all') p.set('o', ov);
    const qs = p.toString();
    return qs ? `/history?${qs}` : '/history';
  };

  const filter = (list: [string, LucideIcon, string][], current: string, key: 's' | 'o') => (
    <div className={s.group}>
      {list.map(([v, Icon, tip]) => (
        <Link key={v} href={href({ [key]: v })} replace scroll={false} className="icon-btn md"
          data-tip={tip} aria-label={tip} aria-current={current === v ? 'true' : undefined}>
          <Icon size={19} strokeWidth={current === v ? 2 : 1.5} />
        </Link>
      ))}
    </div>
  );

  return (
    <>
      <AppHeader date={shortDate(wibDate(now))} title="History" demo={run.isDemo} />
      <div className="stack">
        <section className={`sheet bg-sheet ${s.summary}`}>
          <div className={s.filters}>
            {filter(STRAT_BTNS, strat, 's')}
            {filter(OUT_BTNS, outcome, 'o')}
          </div>
          <div className={s.stats}>
            <div className={s.stat}><span className={`num ${s.big} ${net < 0 ? 'neg' : 'pos'}`}>{signedUsd(net)}</span><span className={s.sub}>Net result</span></div>
            <div className={s.stat}><span className={`num ${s.mid}`}>{wins}</span><span className={s.sub}>Won</span></div>
            <div className={s.stat}><span className={`num ${s.mid}`}>{rows.length - wins}</span><span className={s.sub}>Lost</span></div>
          </div>
          <div className={s.key}>
            {Object.entries(REASON).map(([k, [Icon]]) => (
              <span key={k}><Icon size={15} />{k === 'tp' ? 'Take profit' : k === 'sl' ? 'Stop loss' : k === 'time' ? 'Day 5' : 'Gap'}</span>
            ))}
          </div>
        </section>

        <section className={`sheet over bg-stone ${s.list}`}>
          {rows.length === 0 && <div className={s.none}>No trades match these filters.</div>}
          {rows.map(r => {
            const [RIcon, rTip] = REASON[r.reason] ?? REASON.time;
            const [SIcon, sTip] = STRAT[r.strategyId] ?? STRAT.A;
            const win = r.pnl > 0;
            return (
              <div key={r.id} className={s.row}>
                <span className={s.reason} data-tip={rTip} aria-label={rTip}><RIcon size={19} strokeWidth={1.6} /></span>
                <div className={s.main}>
                  <span className={s.line1}>
                    <span className={s.sym}>{r.symbol}</span>
                    <span className={s.tag} data-tip={sTip}><SIcon size={12} />{r.strategyId}</span>
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
        </section>
      </div>
    </>
  );
}

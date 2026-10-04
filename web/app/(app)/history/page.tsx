import {
  ArrowRightLeft, CircleDashed, CircleSlash, Hourglass, List, OctagonX, SkipForward, Target, TrendingDown, TrendingUp,
  type LucideIcon,
} from 'lucide-react';
import Link from 'next/link';
import { AppHeader } from '@/components/AppHeader';
import { PaperChip } from '@/components/PaperChip';
import { strategyIcon } from '@/components/roster';
import { ALL, StrategySwitch } from '@/components/StrategySwitch';
import { closedTrades, runStatus, strategies } from '@/lib/data';
import { monthDay, money, shortDate, signedPct, signedUsd } from '@/lib/format';
import { wibDate } from '@/lib/session';
import s from './history.module.css';

export const dynamic = 'force-dynamic';

// [icon, tooltip, legend label]
const REASON: Record<string, [LucideIcon, string, string]> = {
  tp: [Target, 'Take profit hit', 'Take profit'],
  sl: [OctagonX, 'Stop loss hit', 'Stop loss'],
  time: [Hourglass, 'Time exit, day 5', 'Day 5'],
  gap: [SkipForward, 'Gapped past stop at open', 'Gap'],
  signal: [ArrowRightLeft, 'Rules said sell, sold at the open', 'Signal'],
  forced: [CircleSlash, 'Forced close, no more prices', 'Forced'],
};
const UNKNOWN_REASON: [LucideIcon, string, string] = [CircleDashed, 'Closed', 'Closed'];
const OUT_BTNS: [string, LucideIcon, string][] = [['all', List, 'Wins and losses'], ['win', TrendingUp, 'Wins only'], ['loss', TrendingDown, 'Losses only']];

type Search = { s?: string; o?: string };

export default async function History({ searchParams }: { searchParams: Promise<Search> }) {
  const now = new Date();
  const q = await searchParams;
  const roster = await strategies();
  const research = roster.filter(r => !r.isBenchmark);
  const strat = q.s && research.some(r => r.id === q.s) ? q.s : ALL;
  const outcome = q.o === 'win' || q.o === 'loss' ? q.o : 'all';
  const [run, rows] = await Promise.all([
    runStatus(now),
    closedTrades(strat === ALL ? null : strat, outcome === 'all' ? null : outcome),
  ]);
  const byId = new Map(roster.map(r => [r.id, r]));
  const net = rows.reduce((a, r) => a + r.pnl, 0);
  const wins = rows.filter(r => r.pnl > 0).length;

  const href = (next: Search) => {
    const p = new URLSearchParams();
    const sv = next.s ?? strat, ov = next.o ?? outcome;
    if (sv !== ALL) p.set('s', sv);
    if (ov !== 'all') p.set('o', ov);
    const qs = p.toString();
    return qs ? `/history?${qs}` : '/history';
  };

  return (
    <>
      <AppHeader date={shortDate(wibDate(now))} title="History" demo={run.isDemo} />
      <div className="stack">
        <section className={`sheet bg-sheet ${s.summary}`}>
          <div className={s.filters}>
            <StrategySwitch strategies={research} current={strat} href={id => href({ s: id })}
              label="Strategy filter" allTip="All strategies" />
            <div className={s.group} role="group" aria-label="Outcome filter">
              {OUT_BTNS.map(([v, Icon, tip]) => (
                <Link key={v} href={href({ o: v })} replace scroll={false} className="icon-btn md"
                  data-tip={tip} aria-label={tip} aria-current={outcome === v ? 'true' : undefined}>
                  <Icon size={19} strokeWidth={outcome === v ? 2 : 1.5} />
                </Link>
              ))}
            </div>
          </div>
          <div className={s.stats}>
            <div className={s.stat}><span className={`num ${s.big} ${net < 0 ? 'neg' : 'pos'}`}>{signedUsd(net)}</span><span className={s.sub}>Net result</span></div>
            <div className={s.stat}><span className={`num ${s.mid}`}>{wins}</span><span className={s.sub}>Won</span></div>
            <div className={s.stat}><span className={`num ${s.mid}`}>{rows.length - wins}</span><span className={s.sub}>Lost</span></div>
          </div>
          <div className={s.key}>
            {Object.entries(REASON).map(([k, [Icon, , label]]) => (
              <span key={k}><Icon size={15} />{label}</span>
            ))}
          </div>
        </section>

        <section className={`sheet over bg-stone ${s.list}`}>
          {rows.length === 0 && <div className={s.none}>No trades match these filters.</div>}
          {rows.map(r => {
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
        </section>
      </div>
    </>
  );
}

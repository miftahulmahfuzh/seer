import { BrainCircuit, Check, Crown, Gavel, Landmark, Sigma, X, type LucideIcon } from 'lucide-react';
import { AppHeader } from '@/components/AppHeader';
import { leaderboard, runStatus, type Board } from '@/lib/data';
import { monthDay, monthName, shortDate, signedPct } from '@/lib/format';
import { checklist } from '@/lib/metrics';
import { wibDate } from '@/lib/session';
import s from './leaderboard.module.css';

export const dynamic = 'force-dynamic';

const ICONS: Record<string, LucideIcon> = { sigma: Sigma, 'brain-circuit': BrainCircuit, gavel: Gavel, landmark: Landmark };
const CARD_BG: Record<string, string> = { A: 'bg-lav', B: 'bg-sky', C: 'bg-stone' };
const LINE: Record<string, string> = { B: 'var(--line-b)', C: 'var(--line-c)' };

const W = 340, H = 170;

export default async function Leaderboard() {
  const now = new Date();
  const [board, run] = await Promise.all([leaderboard(), runStatus(now)]);
  const champ = board.rows.find(r => r.strategy.isChampion);
  const spy = board.rows.find(r => r.strategy.isBenchmark);
  const items = champ ? checklist(champ.metrics, spy?.metrics.totalReturn ?? null, champ.strategy.gate) : [];
  const passed = items.filter(i => i.ok).length;
  const period = board.from && board.to ? `${monthDay(board.from)} – ${monthDay(board.to)}` : 'Not started';
  const chart = buildChart(board);
  const ret = (v: number | null) => (v === null ? '—' : signedPct(v, 1));

  const chartSheet = (
    <section className={`sheet bg-sheet ${s.chartSheet}`}>
      <div className={`${s.between} ${s.pad} mobile-only`}>
        <span className="eyebrow">Forward test</span>
        <span className="pill-outline">{period}</span>
      </div>
      <div className={`${s.headline} ${s.pad}`}>
        <div className={s.stats}>
          <div className={s.stat}>
            <span className={`num ${s.big} ${(champ?.metrics.totalReturn ?? 0) < 0 ? 'neg' : 'pos'}`}>{ret(champ?.metrics.totalReturn ?? null)}</span>
            <span className={s.statLabel}><Crown size={14} /><span>{champ?.strategy.name ?? 'No champion'}<span className="desk-only">, champion</span></span></span>
          </div>
          <div className={s.stat}><span className={`num ${s.mid}`}>{ret(spy?.metrics.totalReturn ?? null)}</span><span className={s.statLabel}>SPY</span></div>
          <div className={`${s.stat} mobile-only`}><span className={`num ${s.mid}`}>{champ?.curve.length ?? 0}</span><span className={s.statLabel}>Sessions</span></div>
        </div>
        <Legend rows={board.rows} className="desk-only" short />
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" className={s.chart} role="img"
        aria-label="Equity curves of each strategy against SPY">
        {chart.grid.map(y => <line key={y} x1="0" x2={W} y1={y} y2={y} vectorEffect="non-scaling-stroke" stroke="var(--hair)" />)}
        <line x1="0" x2={W} y1={chart.zero} y2={chart.zero} vectorEffect="non-scaling-stroke" stroke="var(--outline)" strokeDasharray="3 3" />
        {chart.lines.map(l => (
          <path key={l.id} d={l.d} vectorEffect="non-scaling-stroke" fill="none" stroke={l.color} strokeWidth={l.width}
            strokeDasharray={l.dotted ? '1 4' : undefined} strokeLinecap="round" strokeLinejoin="round" />
        ))}
      </svg>
      <div className={`${s.axis} ${s.pad}`}>{chart.labels.map((l, i) => <span key={i}>{l}</span>)}</div>
      <Legend rows={board.rows} className={`${s.pad} mobile-only`} />
    </section>
  );

  const checklistSheet = (
    <section className={`sheet over bg-butter ${s.check}`}>
      <span className="eyebrow">Go-live checklist · {champ?.strategy.id ?? '—'}</span>
      <div className={s.score}>
        <span className={s.scoreNum}>{passed}/{items.length || 6}</span>
        <span className={s.scoreText}>{items.length > 0 && passed === items.length ? <>All six pass.<br />Ready for real money</> : <>Paper trading until<br />all six pass</>}</span>
      </div>
      {items.map(c => (
        <div key={c.label} className={s.item}>
          {c.ok
            ? <span className={s.ok} aria-label="Passed"><Check size={18} strokeWidth={2.25} /></span>
            : <span className={s.no} aria-label="Not yet"><X size={18} strokeWidth={2.25} /></span>}
          <span className={s.itemLabel}>{c.label}</span>
          <span className={`chip num ${s.itemVal}`}>{c.val}</span>
        </div>
      ))}
    </section>
  );

  return (
    <>
      <AppHeader date={shortDate(wibDate(now))} title="Leaderboard" demo={run.isDemo}
        deskAside={<span className="pill-outline" style={{ height: 52, fontSize: 16, color: 'var(--ink)' }}>Forward test · {period}</span>} />
      <div className="stack">
        <div className={s.top}>{chartSheet}{checklistSheet}</div>
        <div className={s.cards}>
          {board.rows.map(({ strategy: st, metrics: m }) => {
            const Icon = ICONS[st.icon] ?? Sigma;
            const dash = (v: string) => (st.isBenchmark ? '—' : v);
            return (
              <article key={st.id} className={`sheet over ${CARD_BG[st.id] ?? 'bg-sheet'} ${s.card}`}>
                <div className={s.cardHead}>
                  <div className={s.cardName}>
                    <span className={s.name}>{st.name}{st.isChampion && <span data-tip="Champion" className={s.crown}><Crown size={20} /></span>}</span>
                    <span className={s.cardSub}>{st.sub}</span>
                  </div>
                  <span className={s.icon}><Icon size={22} strokeWidth={1.6} /></span>
                </div>
                <div className={s.metrics}>
                  <div className={s.metric}><span className={`num ${s.ret} ${(m.totalReturn ?? 0) < 0 ? 'neg' : 'pos'}`}>{ret(m.totalReturn)}</span><span className={s.mLabel}><span className="mobile-only">Return</span><span className="desk-only">Total return</span></span></div>
                  <div className={s.metric}><span className="num">{dash(m.winRate === null ? '—' : Math.round(m.winRate * 100) + '%')}</span><span className={s.mLabel}>Win rate</span></div>
                  <div className={s.metric}><span className="num">{dash(m.profitFactor === null ? '—' : m.profitFactor === Infinity ? '∞' : m.profitFactor.toFixed(2))}</span><span className={s.mLabel}><span className="mobile-only">Profit f.</span><span className="desk-only">Profit factor</span></span></div>
                  <div className={s.metric}><span className="num">{m.maxDrawdown === null ? '—' : (m.maxDrawdown * 100).toFixed(1) + '%'}</span><span className={s.mLabel}><span className="mobile-only">Max DD</span><span className="desk-only">Max drawdown</span></span></div>
                  <div className={s.metric}><span className="num">{dash(String(m.trades))}</span><span className={s.mLabel}>Trades</span></div>
                </div>
              </article>
            );
          })}
        </div>
        <div className="nav-clear" />
      </div>
    </>
  );
}

function Legend({ rows, className, short }: { rows: Board['rows']; className: string; short?: boolean }) {
  return (
    <div className={`${s.legend} ${className}`}>
      {rows.map(({ strategy: st }) => (
        <span key={st.id} className={s.legendItem}>
          {st.isBenchmark
            ? <span className={s.swatchDot} />
            : <span className={s.swatch} style={{ background: st.isChampion ? 'var(--ink)' : LINE[st.id] ?? 'var(--ink-2)' }} />}
          {short ? st.id : st.isBenchmark ? 'SPY' : `${st.id} ${st.name.split('·')[1]?.trim() ?? ''}`}
        </span>
      ))}
    </div>
  );
}

function buildChart(board: Board) {
  const dates = [...new Set(board.rows.flatMap(r => r.curve.map(c => c.date)))].sort();
  const xi = new Map(dates.map((d, i) => [d, i]));
  const series = board.rows.filter(r => r.curve.length > 1).map(r => ({
    row: r,
    pts: r.curve.map(c => ({ x: xi.get(c.date)!, v: (c.equity / r.curve[0].equity - 1) * 100 })),
  }));
  const all = series.flatMap(s => s.pts.map(p => p.v)).concat(0);
  const lo = Math.min(...all), hi = Math.max(...all);
  const span = hi - lo || 1;
  const y = (v: number) => +(H - 10 - ((v - lo) / span) * (H - 24)).toFixed(1);
  const x = (i: number) => +((i / Math.max(1, dates.length - 1)) * W).toFixed(1);

  // Champion last so it draws on top.
  const ordered = [...series].sort((a, b) => Number(a.row.strategy.isChampion) - Number(b.row.strategy.isChampion));
  const lines = ordered.map(({ row, pts }) => ({
    id: row.strategy.id,
    d: pts.map((p, i) => `${i ? 'L' : 'M'}${x(p.x)} ${y(p.v)}`).join(' '),
    color: row.strategy.isChampion ? 'var(--ink)' : row.strategy.isBenchmark ? 'var(--ink-3)' : LINE[row.strategy.id] ?? 'var(--ink-2)',
    width: row.strategy.isChampion ? 2.75 : row.strategy.isBenchmark ? 1.75 : 2,
    dotted: row.strategy.isBenchmark,
  }));

  const labels: string[] = [];
  if (dates.length) {
    labels.push(monthDay(dates[0]));
    const first = monthName(dates[0]), last = monthName(dates[dates.length - 1]);
    for (const m of [...new Set(dates.map(monthName))]) if (m !== first && m !== last) labels.push(m);
    if (dates.length > 1) labels.push(monthDay(dates[dates.length - 1]));
  }
  return { lines, labels, zero: y(0), grid: [y(hi), y((hi + lo) / 2)] };
}

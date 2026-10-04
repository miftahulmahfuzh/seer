import { Crown } from 'lucide-react';
import { AppHeader } from '@/components/AppHeader';
import { champion, positions as getPositions, runStatus } from '@/lib/data';
import { shortDate, signedPct, signedRp, signedUsd, usd } from '@/lib/format';
import { wibDate } from '@/lib/session';
import { SLOT_BG } from '@/lib/slots';
import s from './positions.module.css';

export const dynamic = 'force-dynamic';

export default async function Positions() {
  const now = new Date();
  const [champ, run] = await Promise.all([champion(), runStatus(now)]);
  const open = champ ? await getPositions(champ.id) : [];
  const pnl = open.reduce((a, p) => a + (p.current - p.entry) * p.shares, 0);
  const exitsToday = open.filter(p => p.maxDays !== null && p.day >= p.maxDays).length;

  return (
    <>
      <AppHeader date={shortDate(wibDate(now))} title="Positions" demo={run.isDemo} />
      <div className="stack">
        <section className={`sheet bg-sheet ${s.summary}`}>
          <div className={s.between}>
            <span className="eyebrow">Unrealized P/L</span>
            <span className="pill-outline"><Crown size={15} />Strategy {champ?.id ?? '—'}</span>
          </div>
          <div className={s.stats}>
            <div className={`${s.stat} ${pnl < 0 ? 'neg' : 'pos'}`}>
              <span className={`num ${s.big}`}>{signedUsd(pnl)}</span>
              <span className={s.sub}>{signedRp(pnl, run.usdIdr)}</span>
            </div>
            <div className={s.stat}><span className={s.mid}>{open.length}</span><span className={s.sub}>Open</span></div>
            <div className={s.stat}><span className={s.mid}>{exitsToday}</span><span className={s.sub}>Exits today</span></div>
          </div>
        </section>

        {open.length === 0 ? (
          <section className={`sheet over bg-stone ${s.none}`}>No open positions.</section>
        ) : (
          <div className={s.grid}>
            {open.map((q, i) => {
              const sl = q.sl ?? Math.min(q.entry, q.current), tp = q.tp ?? Math.max(q.entry, q.current);
              const range = tp - sl || 1;
              const at = (v: number) => Math.min(100, Math.max(0, ((v - sl) / range) * 100));
              const e = at(q.entry), c = at(q.current), up = q.current >= q.entry;
              const d = (q.current - q.entry) * q.shares;
              return (
                <article key={q.key} className={`sheet over ${SLOT_BG[i % 4]} ${s.card}`}>
                  <div className={s.head}>
                    <div className={s.ticker}>
                      <span className={s.sym}>{q.symbol}</span>
                      <span className={s.company}>{q.company} · {q.shares === 1 ? '1 share' : `${q.shares} shares`}</span>
                    </div>
                    <div className={`${s.change} ${up ? 'pos' : 'neg'}`}>
                      <span className={`num ${s.pct}`}>{signedPct(q.current / q.entry - 1)}</span>
                      <span className="num">{signedUsd(d)}</span>
                    </div>
                  </div>
                  <div className={s.chips}>
                    <span className="chip num">Entry {usd(q.entry)}</span>
                    <span className="chip num" style={{ background: 'var(--chip-solid)', fontWeight: 500 }}>Now {usd(q.current)}</span>
                  </div>
                  <div className={s.range}>
                    <div className={`num ${s.between}`} style={{ fontSize: 15 }}><span>Stop {q.sl === null ? '—' : usd(q.sl)}</span><span>Target {q.tp === null ? '—' : usd(q.tp)}</span></div>
                    <div className={s.track} role="img" aria-label={`Price is ${Math.round(c)}% of the way from stop to target`}>
                      <div className={s.fill} style={{ left: `${Math.min(e, c)}%`, width: `${Math.abs(c - e)}%`, background: up ? 'var(--pos)' : 'var(--neg)' }} />
                      <div className={s.entry} style={{ left: `${e}%` }} />
                      <div className={s.cur} style={{ left: `${c}%` }} />
                    </div>
                  </div>
                  <div className={s.between}>
                    <div className={s.days} aria-hidden="true">
                      {[1, 2, 3, 4, 5].map(k => <span key={k} className={k <= q.day ? s.dayOn : s.dayOff} />)}
                    </div>
                    <span className={s.dayLabel}>{q.day >= 5 ? `Day ${q.day}/5 · exit today` : `Day ${q.day}/5`}</span>
                  </div>
                </article>
              );
            })}
          </div>
        )}
        <div className="nav-clear" />
      </div>
    </>
  );
}

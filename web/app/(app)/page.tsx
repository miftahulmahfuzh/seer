import { Check, Crown, TriangleAlert } from 'lucide-react';
import { AppHeader } from '@/components/AppHeader';
import { CopyButton } from '@/components/CopyButton';
import { RefreshButton } from '@/components/RefreshButton';
import { WhyToggle } from '@/components/WhyToggle';
import { champion, picks as getPicks, positions as getPositions, runStatus, type Pick } from '@/lib/data';
import { money, monthDay, rp, shortDate, signedRp, signedUsd, usd } from '@/lib/format';
import { wibDate } from '@/lib/session';
import { SLOT_BG, SLOT_LETTERS, slotBg, slotLetter } from '@/lib/slots';
import { dismiss } from './actions';
import s from './today.module.css';

export const dynamic = 'force-dynamic';

const ORDINAL = ['first', 'second', 'third', 'fourth'];
const WIB_TIME = new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Jakarta', hour: '2-digit', minute: '2-digit' });

export default async function Today() {
  const now = new Date();
  const [champ, run] = await Promise.all([champion(), runStatus(now)]);
  const showPicks = !!champ && !!run.sessionDate && !run.stale;
  const [picks, open] = await Promise.all([
    showPicks ? getPicks(champ.id, run.sessionDate!) : Promise.resolve([] as Pick[]),
    champ ? getPositions(champ.id) : Promise.resolve([]),
  ]);
  const actions = open.filter(p => p.day >= 5 && !p.dismissed);
  const filled = new Set(picks.map(p => p.slot));
  const emptySlots = [1, 2, 3, 4].filter(n => !filled.has(n));
  const session = run.sessionDate ? shortDate(run.sessionDate) : '—';
  const stratLabel = champ ? `Strategy ${champ.id} · ${champ.sub}` : 'No champion yet';

  return (
    <>
      <AppHeader
        date={shortDate(wibDate(now))}
        title="Today"
        deskTitle={run.stale ? 'Today' : `Picks for US session ${session}`}
        deskAside={<span className="pill-outline" style={{ height: 52, fontSize: 16, color: 'var(--ink)' }}><Crown size={16} />{stratLabel}</span>}
        demo={run.isDemo}
      />

      <div className="stack">
        <section className={`sheet bg-sheet mobile-only ${s.summary}`}>
          <div className={s.between}>
            <span className="eyebrow">US session</span>
            <span className="pill-outline" style={{ fontSize: 16, padding: '0 20px' }}>{session}</span>
          </div>
          <div className={s.between} style={{ alignItems: 'flex-end' }}>
            <div className={s.count}>
              <span className={s.countNum}>{run.stale ? '—' : picks.length}</span>
              <span className={s.countLabel}>Picks tonight</span>
            </div>
            <div className={s.slotsCol}>
              <div className="slot-dots" aria-label={`${picks.length} of 4 slots filled`}>
                {SLOT_LETTERS.map((l, i) => (
                  <span key={i} className={`slot-dot ${filled.has(i + 1) ? SLOT_BG[i] : 'empty'}`}>{l}</span>
                ))}
              </div>
              <span className={s.strat}><Crown size={15} />{stratLabel}</span>
            </div>
          </div>
        </section>

        {run.stale ? (
          <section className={`sheet over ${s.alarm}`}>
            <div className={s.between}>
              <span className={s.alarmIcon}><TriangleAlert size={28} /></span>
              <RefreshButton className={`icon-btn ${s.alarmBtn}`} />
            </div>
            <span className={s.alarmTitle}>
              {run.dataDate ? `Data is from ${monthDay(run.dataDate)}. Do not trade today.` : 'No data yet. Do not trade today.'}
            </span>
            <span className={s.alarmSub}>
              {run.finishedAt
                ? `Last good run ${shortDate(wibDate(run.finishedAt))} at ${WIB_TIME.format(run.finishedAt)} WIB. Picks stay hidden until fresh prices arrive.`
                : 'The nightly engine has not completed a run yet. Picks stay hidden until it does.'}
            </span>
          </section>
        ) : picks.length === 0 ? (
          <section className={`sheet over bg-stone ${s.none}`}>
            <span>No setups today.</span>
            <span style={{ color: 'var(--ink-3)' }}>Cash is a position.</span>
          </section>
        ) : (
          <div className={s.board}>
            {actions.map(a => (
              <section key={a.id} className={`sheet over bg-coral ${s.action}`}>
                <span className="eyebrow">Action needed</span>
                <div className={s.actionRow}>
                  <span className={s.actionText}><b>{a.symbol}</b>: day {a.day} of 5. Cancel bracket and sell at market.</span>
                  <form action={dismiss}>
                    <input type="hidden" name="orderId" value={a.id} />
                    <button type="submit" className={`icon-btn ${s.onCoral}`} data-tip="Mark as done" aria-label="Mark as done">
                      <Check size={22} />
                    </button>
                  </form>
                </div>
              </section>
            ))}

            <div className={s.grid}>
              {picks.map(p => <PickCard key={p.id} p={p} rate={run.usdIdr} />)}
              {emptySlots.map(n => (
                <section key={n} className={`${s.emptySlot} desk-only`}>
                  <span className={s.emptyDot}>{slotLetter(n)}</span>
                  <span className={s.emptyTitle}>Empty slot</span>
                  <span className={s.emptySub}>No {ORDINAL[n - 1]} stock passed the rules tonight.</span>
                </section>
              ))}
            </div>

            {emptySlots.length > 0 && (
              <section className={`sheet over bg-sheet mobile-only ${s.emptyRow}`}>
                <span className={s.emptyDot}>{slotLetter(emptySlots[0])}</span>
                <div className={s.emptyText}>
                  <span className={s.emptyTitle}>{emptySlots.length === 1 ? 'Empty slot' : `${emptySlots.length} empty slots`}</span>
                  <span className={s.emptySub}>
                    {emptySlots.length === 1 ? `No ${ORDINAL[emptySlots[0] - 1]} stock passed the rules tonight.` : `Only ${picks.length} passed the rules tonight.`}
                  </span>
                </div>
              </section>
            )}
          </div>
        )}
        <div className="nav-clear" />
      </div>
    </>
  );
}

function PickCard({ p, rate }: { p: Pick; rate: number }) {
  const cost = p.limit * p.shares, profit = (p.tp - p.limit) * p.shares, loss = (p.limit - p.sl) * p.shares;
  const fields = [
    { label: 'Limit buy', unit: '$', value: money(p.limit), tip: 'Copy limit price' },
    { label: 'Take profit', unit: '$', value: money(p.tp), tip: 'Copy take-profit price' },
    { label: 'Stop loss', unit: '$', value: money(p.sl), tip: 'Copy stop-loss price' },
    { label: 'Shares', unit: '', value: String(p.shares), tip: 'Copy number of shares' },
  ];
  return (
    <article className={`sheet over ${slotBg(p.slot)} ${s.pick}`}>
      <div className={s.pickHead}>
        <div className={s.ticker}>
          <span className={s.sym}>{p.symbol}</span>
          <span className={s.company}>{p.company}</span>
        </div>
        <span className={s.slot}>{slotLetter(p.slot)}</span>
      </div>
      <div className={s.lastRow}>
        <span className="chip num">Last {usd(p.last)}</span>
        <span className={`${s.bracket} mobile-only`}>Bracket order, exits by day 5</span>
      </div>
      <div className={s.fields}>
        {fields.map(f => (
          <div key={f.label} className={s.field}>
            <span className={s.fieldLabel}>{f.label}</span>
            <div className={s.fieldRow}>
              <span className={`num ${s.fieldVal}`}><span className={s.unit}>{f.unit}</span><span className={s.value}>{f.value}</span></span>
              <CopyButton value={f.value} tip={f.tip} />
            </div>
          </div>
        ))}
      </div>
      <div className={s.est}>
        <div className={s.estItem}><span className={s.estLabel}>Est. cost</span><span className={s.estVals}><span className={s.estUsd}>{usd(cost)}</span><span className={s.estIdr}>{rp(cost, rate)}</span></span></div>
        <div className={`${s.estItem} pos`}><span className={s.estLabel}>Est. profit</span><span className={s.estVals}><span className={s.estUsd}>{signedUsd(profit)}</span><span className={s.estIdr}>{signedRp(profit, rate)}</span></span></div>
        <div className={`${s.estItem} neg`}><span className={s.estLabel}>Est. loss</span><span className={s.estVals}><span className={s.estUsd}>{signedUsd(-loss)}</span><span className={s.estIdr}>{signedRp(-loss, rate)}</span></span></div>
      </div>
      <WhyToggle text={p.explanation} />
    </article>
  );
}

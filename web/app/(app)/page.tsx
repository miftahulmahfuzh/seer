import { Check, Clock, Crown, Pause, TriangleAlert } from 'lucide-react';
import { AppHeader } from '@/components/AppHeader';
import { CopyButton } from '@/components/CopyButton';
import { RefreshButton } from '@/components/RefreshButton';
import { WhyToggle } from '@/components/WhyToggle';
import {
  champion, picks as getPicks, positions as getPositions, runStatus,
  type Holding, type Pick, type RunStatus, type Strategy,
} from '@/lib/data';
import { PAPER_PAUSED, pipelineState, timing, type PipelineState, type Timing } from '@/lib/decision';
import { companyName, money, monthDay, rp, shortDate, signedRp, signedUsd, usd } from '@/lib/format';
import { wibDate, wibTime } from '@/lib/session';
import { SLOT_BG, SLOT_LETTERS, slotBg, slotLetter } from '@/lib/slots';
import { dismiss } from './actions';
import s from './today.module.css';

export const dynamic = 'force-dynamic';

const ORDINAL = ['first', 'second', 'third', 'fourth'];

/** Only a bracket champion that is not the benchmark makes buy picks. With SPY as champion (D2), none does. */
const picksChampion = (c: Strategy | null): Strategy | null =>
  c && !c.isBenchmark && c.engine === 'bracket' ? c : null;

const champLabel = (c: Strategy | null) =>
  !c ? 'No champion yet' : c.isBenchmark ? `${c.name} · ${c.sub}` : `Strategy ${c.id} · ${c.sub}`;

const noBuysTitle = (c: Strategy | null) =>
  !c ? 'No champion yet.' : c.isBenchmark ? `${c.name} buy-and-hold is the champion.` : `${c.name} is the champion.`;

export default async function Today() {
  const now = new Date();
  const [champ, run] = await Promise.all([champion(), runStatus(now)]);
  const pc = picksChampion(champ);
  const [picks, open] = await Promise.all([
    pc && run.sessionDate && !run.stale ? getPicks(pc.id, run.sessionDate) : Promise.resolve([] as Pick[]),
    pc ? getPositions(pc.id) : Promise.resolve([] as Holding[]),
  ]);
  // Handover Q5: `run.stale` alone used to raise a coral alarm on the ordinary day after the New
  // York close. Only two of its states are actually wrong — no run has ever finished, or the run
  // that owed today's picks missed its last retry at 19:41 WIB.
  const pipeline = pipelineState(run.sessionDate, run.finishedAt, now);
  const when = timing(now);
  const alarm = pipeline === 'never' || pipeline === 'late';
  // Phase 10's guard, kept: only a bracket holding with an order id and a time exit has a day-5 action.
  const actions = open.filter(p => p.orderId !== null && p.maxDays !== null && p.day >= p.maxDays && !p.dismissed);
  const filled = new Set(picks.map(p => p.slot));
  const emptySlots = [1, 2, 3, 4].filter(n => !filled.has(n));
  const session = run.sessionDate ? shortDate(run.sessionDate) : '—';
  const stratLabel = champLabel(champ);

  return (
    <>
      <AppHeader
        date={shortDate(wibDate(now))}
        title="Today"
        deskTitle={run.stale ? 'Today' : pc ? `Picks for US session ${session}` : `US session ${session}`}
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
              <span className={s.countLabel}>{pc ? 'Picks tonight' : 'Buys tonight'}</span>
            </div>
            <div className={s.slotsCol}>
              {pc && (
                <div className="slot-dots" aria-label={`${picks.length} of 4 slots filled`}>
                  {SLOT_LETTERS.map((l, i) => (
                    <span key={i} className={`slot-dot ${filled.has(i + 1) ? SLOT_BG[i] : 'empty'}`}>{l}</span>
                  ))}
                </div>
              )}
              <span className={s.strat}><Crown size={15} />{stratLabel}</span>
            </div>
          </div>
        </section>

        {PAPER_PAUSED && <PausedNote />}

        {alarm ? (
          <section className={`sheet over ${s.alarm}`}>
            <div className={s.between}>
              <span className={s.alarmIcon}><TriangleAlert size={28} /></span>
              <RefreshButton className={`icon-btn ${s.alarmBtn}`} />
            </div>
            <span className={s.alarmTitle}>{alarmTitle(pipeline, when)}</span>
            <span className={s.alarmSub}>{alarmSub(pipeline, run, when)}</span>
          </section>
        ) : pipeline === 'waiting' ? (
          <section className={`sheet over bg-stone ${s.waiting}`} role="status">
            <div className={s.waitingHead}>
              <span className={s.waitingIcon} aria-hidden="true"><Clock size={24} /></span>
              <span className="eyebrow">Nothing to do yet</span>
            </div>
            <span className={s.waitingTitle}>
              {run.sessionDate ? `The ${shortDate(run.sessionDate)} US session has closed.` : 'The last US session has closed.'}
            </span>
            <span className={s.waitingSub}>
              The next picks are due {shortDate(wibDate(when.dueAt))} at {wibTime(when.dueAt)} WIB.
              {run.finishedAt ? ` The last good run finished ${shortDate(wibDate(run.finishedAt))} at ${wibTime(run.finishedAt)} WIB.` : ''}
            </span>
            <span className={s.waitingSub}>Nothing on this page is a live instruction until then.</span>
          </section>
        ) : !pc ? (
          <section className={`sheet over bg-stone ${s.none}`}>
            <span>{noBuysTitle(champ)}</span>
            <span style={{ color: 'var(--ink-3)' }}>Seer recommends no buys.</span>
            <span className={s.noneSub}>
              Research strategies trade on paper only, with no real money. Their orders are in Positions, never here.
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
              <section key={a.key} className={`sheet over bg-coral ${s.action}`}>
                <span className="eyebrow">Action needed</span>
                <div className={s.actionRow}>
                  <span className={s.actionText}><b>{a.symbol}</b>: day {a.day} of {a.maxDays}. Cancel bracket and sell at market.</span>
                  <form action={dismiss}>
                    <input type="hidden" name="orderId" value={a.orderId ?? ''} />
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
        {/* The alarm sheet runs to the bottom edge itself; a spacer under it would only show page
            background. Every other branch, the `waiting` sheet included, needs the spacer. */}
        {!alarm && <div className="nav-clear" />}
      </div>
    </>
  );
}

/**
 * The coral alarm is for the two states that are actually wrong: no run has ever finished, or the
 * run that owed today's picks missed its last retry. Routine daily expiry is the `waiting` sheet
 * instead, which says when the next picks arrive. The old single alarm read "Data is from Oct 7. Do
 * not trade today." at 08:17 WIB on a morning when the run was not due until 13:17 WIB.
 */
function alarmTitle(pipeline: PipelineState, when: Timing): string {
  if (pipeline === 'never') return 'No data yet. Do not trade today.';
  return `No picks for ${monthDay(when.target)}. Do not trade today.`;
}

function alarmSub(pipeline: PipelineState, run: RunStatus, when: Timing): string {
  if (pipeline === 'never') return 'The nightly engine has not completed a run yet. Picks stay hidden until it does.';
  const due = `The run was due at ${wibTime(when.dueAt)} WIB and its last retry was ${wibTime(when.lateAfter)} WIB.`;
  const last = run.finishedAt
    ? ` Last good run ${shortDate(wibDate(run.finishedAt))} at ${wibTime(run.finishedAt)} WIB${run.dataDate ? `, from the ${monthDay(run.dataDate)} closes` : ''}.`
    : '';
  return `${due}${last} Picks stay hidden until fresh prices arrive.`;
}

/**
 * Paper trading is switched off (`PAPER_PAUSED` in `.github/workflows/nightly.yml`). The fifth state
 * of handover Q5. The nightly's price step still runs, so this page's data is unaffected; what is
 * frozen is every paper order and paper session behind Positions.
 */
function PausedNote() {
  return (
    <section className={`sheet over bg-butter ${s.paused}`} role="status">
      <span className={s.pausedIcon} aria-hidden="true"><Pause size={20} /></span>
      <div className={s.pausedText}>
        <span className={s.pausedTitle}>Paper trading is paused</span>
        <span className={s.pausedSub}>
          No paper orders are placed and no paper session is stepped while the roster is rebuilt to
          pay the real broker fees. Prices are still updated every night.
        </span>
      </div>
    </section>
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
          {companyName(p.company, p.symbol) && <span className={s.company}>{p.company}</span>}
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
      <WhyToggle text={p.explanation} facts={p.evidence} />
    </article>
  );
}

import { Check, CircleMinus, CirclePlus, Link2Off, RotateCcw } from 'lucide-react';
import type { Metadata } from 'next';
import { sharesLabel, strategyIcon } from '@/components/roster';
import { PageHeader } from '@/components/sera/PageHeader';
import { Section } from '@/components/sera/Section';
import { Stat } from '@/components/sera/Stat';
import { shortDate, usd } from '@/lib/format';
import { requireSean } from '@/lib/sean/gate';
import { orderSession } from '@/lib/sean/ledger';
import { linkableMethods, planState, type LinkableMethod, type PlanState } from '@/lib/sean/planData';
import type { Reminder } from '@/lib/sean/reminders';
import { markDone, undoDone, unlinkMethod } from './actions';
import { LinkPicker } from './LinkPicker';
import { PlanSettings } from './PlanSettings';
import {
  cashLine, doneLine, methodTitle, outsideLine, picksLine, planSizeLine, reminderDetail,
  reminderTitle, todoLabel,
} from './view';
import s from './plan.module.css';

export const metadata: Metadata = { title: 'Plan' };

// Reads and writes Neon on every visit: never prerendered.
export const dynamic = 'force-dynamic';

type Loaded = { ok: true; state: PlanState | null; methods: LinkableMethod[] } | { ok: false };

async function load(): Promise<Loaded> {
  try {
    const [state, methods] = await Promise.all([planState(), linkableMethods()]);
    return { ok: true, state, methods };
  } catch (e) {
    console.error('sean plan read failed', e);
    return { ok: false };
  }
}

export default async function PlanPage() {
  await requireSean('/sean/plan');
  const loaded = await load();
  if (!loaded.ok) {
    return (
      <>
        <PageHeader eyebrow="Plan" title="Follow a method" />
        <Section eyebrow="Plan" title="Can't read the plan right now">
          <p className={s.empty}>Nothing has changed; try again in a moment.</p>
        </Section>
      </>
    );
  }
  // The start date a method with no pick yet defaults to: today's New York date, the calendar
  // plan membership is counted in (plan Decisions).
  if (!loaded.state) return <Unlinked methods={loaded.methods} today={orderSession(new Date().toISOString())} />;
  return <Linked state={loaded.state} />;
}

function Unlinked({ methods, today }: { methods: LinkableMethod[]; today: string }) {
  return (
    <>
      <PageHeader
        eyebrow="Plan"
        title="Follow a method"
        lede="Pick one method from Seer's roster. Sean compares its picks with what you bought for it and tells you what to buy and sell."
      />
      <div className={s.page}>
        <Section eyebrow="Roster" title="Pick a method"
          caption="Only methods that hold a basket of stocks can be followed. Orders from the start date on count toward the plan; anything you bought earlier stays out of it.">
          <LinkPicker methods={methods} today={today} />
        </Section>
      </div>
    </>
  );
}

function Linked({ state }: { state: PlanState }) {
  const { link, targets, plan, outside } = state;
  const Icon = strategyIcon(link.icon);
  const picks = targets?.targets.length ?? 0;
  const heldPicks = plan.holdings.filter(h => h.picked).length;
  const sessionDate = targets?.sessionDate ?? link.since;
  const lede = link.retired
    ? `${link.short} has left Seer's roster, so there are no picks to follow. Stop following it and pick another method.`
    : targets
      ? picksLine({ short: link.short, sessionDate: targets.sessionDate, pending: targets.pending, count: picks, rulesId: link.rulesId })
      : `${link.short} has not picked any stocks yet. Reminders show up after its first pick.`;
  const unlinkTip = `Stop following ${link.short}`;
  const outsideNote = outsideLine(outside, link.since);

  return (
    <>
      <PageHeader
        eyebrow="Plan"
        title={`Following ${link.short}`}
        lede={lede}
        aside={
          <form action={unlinkMethod}>
            <button type="submit" className="icon-btn" aria-label={unlinkTip} data-tip={unlinkTip}>
              <Link2Off size={21} strokeWidth={1.5} />
            </button>
          </form>
        }
      />
      <div className={s.page}>
        <Section className={s.summary}>
          <div className={s.method}>
            <span className={s.methodIcon} aria-hidden="true"><Icon size={24} strokeWidth={1.5} /></span>
            <span className={s.methodText}>
              <span className={s.methodName}>{methodTitle(link.name)}</span>
              <span className={s.methodSub}>{link.sub}</span>
            </span>
          </div>
          <div className={s.stats}>
            <Stat value={String(plan.open.length)} label="To do" size="md" tip="Reminders still waiting for you" />
            <Stat value={plan.planSize === null ? '—' : usd(plan.planSize)} label="Plan size" size="md"
              sub={cashLine(plan.planSize, plan.cashUsd, link.budgetUsd)}
              tip="What the picks are sized against: the stocks this plan holds plus the cash you have added since it started" />
            <Stat value={`${heldPicks} of ${picks}`} label="Picks held" size="md"
              tip={`How many of ${link.short}'s picks your plan holds`} />
          </div>
        </Section>

        <Section eyebrow={todoLabel(plan.open.length)} title="To do"
          caption={plan.open.length > 0
            ? `Sells first: they free the money for the buys. A reminder clears when you upload the order, or when you mark it done.`
            : `Your plan matches ${link.short}'s picks. New reminders show up after its next pick.`}>
          {plan.open.length > 0 && (
            <ul className={s.list}>
              {plan.open.map(r => (
                <ReminderRow key={r.key} r={r} short={link.short} sessionDate={sessionDate} />
              ))}
            </ul>
          )}
        </Section>

        {plan.done.length > 0 && (
          <Section bg="stone" eyebrow="Done" title="Already done"
            caption={`Reminders for ${shortDate(sessionDate)} that you have taken care of.`}>
            <ul className={s.list}>
              {plan.done.map(r => (
                <DoneRow key={r.key} r={r} sessionDate={sessionDate} />
              ))}
            </ul>
          </Section>
        )}

        <Section eyebrow={`Since ${shortDate(link.since)}`} title="Your plan"
          caption={planSizeLine(plan.planSize, link.budgetUsd, plan.cashUsd)}>
          <PlanSettings since={link.since} budget={link.budgetUsd} opening={link.openingUsd} />
          {plan.holdings.length === 0 ? (
            <p className={s.empty}>
              Nothing bought for this plan yet. Upload your order screenshots on the Trades tab and they show up here.
            </p>
          ) : (
            <table className={s.table}>
              <thead>
                <tr>
                  <th scope="col">Stock</th>
                  <th scope="col" className={s.right}>Shares</th>
                  <th scope="col" className={s.right}>Price</th>
                  <th scope="col" className={s.right}>Value</th>
                  <th scope="col">{link.short}</th>
                </tr>
              </thead>
              <tbody>
                {plan.holdings.map(h => (
                  <tr key={h.symbol}>
                    <th scope="row" className={`num ${s.symbol}`}>{h.symbol}</th>
                    <td className={`num ${s.right}`}>{sharesLabel(h.shares)}</td>
                    <td className={`num ${s.right}`}>{usd(h.price)}</td>
                    <td className={`num ${s.right}`}>{usd(h.value)}</td>
                    <td className={s.muted}>{h.picked ? 'Picked' : 'No longer picked'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {outsideNote && <p className={s.note}>{outsideNote}</p>}
        </Section>
      </div>
    </>
  );
}

function ReminderRow({ r, short, sessionDate }: { r: Reminder; short: string; sessionDate: string }) {
  const title = reminderTitle(r);
  const tip = `Mark done: ${title}`;
  const Mark = r.side === 'buy' ? CirclePlus : CircleMinus;
  return (
    <li className={s.row}>
      <span className={s.todoMark} aria-hidden="true"><Mark size={20} strokeWidth={1.75} /></span>
      <span className={s.rowText}>
        <span className={`num ${s.rowTitle}`}>{title}</span>
        <span className={s.rowDetail}>{reminderDetail(r, short)}</span>
      </span>
      <form action={markDone}>
        <input type="hidden" name="sessionDate" value={sessionDate} />
        <input type="hidden" name="symbol" value={r.symbol} />
        <input type="hidden" name="side" value={r.side} />
        <button type="submit" className={`icon-btn sm ${s.doneBtn}`} aria-label={tip} data-tip={tip}>
          <Check size={18} strokeWidth={1.75} />
        </button>
      </form>
    </li>
  );
}

function DoneRow({ r, sessionDate }: { r: Reminder; sessionDate: string }) {
  const title = reminderTitle(r);
  const tip = `Not done yet: ${title}`;
  return (
    <li className={s.row}>
      <span className={s.doneMark} aria-hidden="true"><Check size={20} strokeWidth={1.75} /></span>
      <span className={s.rowText}>
        <span className={`num ${s.rowTitle} ${s.struck}`}>{title}</span>
        <span className={s.rowDetail}>{doneLine(r, sessionDate)}</span>
      </span>
      {r.done === 'mark' && (
        <form action={undoDone}>
          <input type="hidden" name="sessionDate" value={sessionDate} />
          <input type="hidden" name="symbol" value={r.symbol} />
          <input type="hidden" name="side" value={r.side} />
          <button type="submit" className="icon-btn sm" aria-label={tip} data-tip={tip}>
            <RotateCcw size={18} strokeWidth={1.5} />
          </button>
        </form>
      )}
    </li>
  );
}

import {
  ArrowUpRight, Database, FlaskRound, Layers, ListFilter, Sparkles, TriangleAlert, Wrench, type LucideIcon,
} from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';
import { PageHeader } from '@/components/sera/PageHeader';
import { Section } from '@/components/sera/Section';
import { requireSera } from '@/lib/sera/gate';
import { INSIGHT_KIND_LABEL } from '@/lib/sera/glossary';
import { lab, methodById } from '@/lib/sera/lab';
import { renderMarkdown } from '@/lib/sera/markdown';
import { seenInsightIds } from '@/lib/sera/seen';
import { INSIGHT_KINDS, type InsightKind, type LabInsight } from '@/lib/sera/types';
import {
  SEEN_COPY, badgeTip, dayLabel, journalGroups, journalHref, kindCounts, parseKind, unseenCounts,
  type KindFilter,
} from './view';
import s from './journal.module.css';

// The layout's title template renders this as "Journal · Sera".
export const metadata: Metadata = { title: 'Journal' };

// The page reads journal_seen from Neon, so it is never cached — the (app) convention.
export const dynamic = 'force-dynamic';

const KIND_ICON: Record<InsightKind, LucideIcon> = {
  synthesis: Layers,
  observation: Sparkles,
  hypothesis: FlaskRound,
  'data-wish': Database,
  'feature-wish': Wrench,
  risk: TriangleAlert,
};

type Search = { kind?: string | string[] };

export default async function JournalPage({ searchParams }: { searchParams: Promise<Search> }) {
  const q = await searchParams;
  const filter = parseKind(q.kind);
  await requireSera(journalHref(filter));
  const seenIds = await seenInsightIds();
  const counts = kindCounts(lab.insights);
  const fresh = unseenCounts(lab.insights, seenIds);
  const groups = journalGroups(lab.insights, filter, seenIds);
  const total = lab.insights.length;

  // heading + total ride along on every option: they are badgeTip's other two arguments, and the
  // client island (phase 4) reads them off this array to keep the tooltip honest as `n` falls.
  const options: { id: KindFilter; heading: string; total: number; tip: string; n: number; Icon: LucideIcon }[] = [
    {
      id: 'all',
      heading: 'Everything',
      total,
      tip: badgeTip('Everything', fresh.all, total),
      n: fresh.all,
      Icon: ListFilter,
    },
    ...INSIGHT_KINDS.map(k => ({
      id: k as KindFilter,
      heading: INSIGHT_KIND_LABEL[k].heading,
      total: counts[k],
      tip: badgeTip(INSIGHT_KIND_LABEL[k].heading, fresh[k], counts[k]),
      n: fresh[k],
      Icon: KIND_ICON[k],
    })),
  ];

  return (
    <>
      <PageHeader
        eyebrow="Journal"
        title="What the lab is thinking"
        lede="Everything the lab noticed along the way: lessons, hunches, the data and tools it wishes it had, and the risks it sees. Food for thought, newest first."
        asOf={lab.asOf}
      />
      <div className={s.page}>
        <div className={s.bar}>
          <nav className="seg" aria-label="Show one kind of entry">
            {options.map(({ id, tip, n, Icon }) => {
              const on = id === filter;
              return (
                <Link key={id} href={journalHref(id)} replace scroll={false} className={`icon-btn md ${s.segBtn}`}
                  data-tip={tip} aria-label={tip} aria-current={on ? 'true' : undefined}>
                  <Icon size={19} strokeWidth={on ? 2 : 1.5} />
                  <span className={`${s.badge} ${n === 0 ? s.zero : ''}`} aria-hidden="true">{n}</span>
                </Link>
              );
            })}
          </nav>
          <p className={s.barNote}>
            {total} {total === 1 ? 'entry' : 'entries'} in all. Every lab run adds to this page.
          </p>
        </div>

        {groups.map(g => {
          const n = g.items.length;
          return (
            <Section
              key={g.kind}
              eyebrow={`${n} ${n === 1 ? 'entry' : 'entries'}`}
              title={g.heading}
              caption={g.caption}
            >
              {n === 0 ? (
                <p className={s.empty}>{g.empty}</p>
              ) : (
                <div className={s.cards}>
                  {g.unseen.map(e => (
                    <InsightCard key={e.insight.id} insight={e.insight} tone={g.tone} unseen />
                  ))}
                  {g.unseenCount > 0 && g.unseenCount < n && (
                    <p className={s.boundary}>{SEEN_COPY.boundary}</p>
                  )}
                  {g.seen.map(e => (
                    <InsightCard key={e.insight.id} insight={e.insight} tone={g.tone} unseen={false} />
                  ))}
                </div>
              )}
            </Section>
          );
        })}
      </div>
    </>
  );
}

function InsightCard({ insight, tone, unseen }: { insight: LabInsight; tone: string; unseen: boolean }) {
  const method = insight.methodId ? methodById(insight.methodId) : undefined;
  return (
    <article
      className={`${s.card} ${tone}`}
      data-insight-id={insight.id}
      data-unseen={unseen ? 'true' : 'false'}
    >
      <header className={s.cardHead}>
        <h3 className={s.cardTitle}>
          <span className={s.new} data-tip={SEEN_COPY.marker}>
            <span className={s.sr}>{SEEN_COPY.markerLabel}: </span>
          </span>
          {insight.title}
        </h3>
        <time className={s.date} dateTime={insight.added}>{dayLabel(insight.added)}</time>
      </header>
      <div className={s.body} dangerouslySetInnerHTML={{ __html: renderMarkdown(insight.body) }} />
      {insight.methodId && (
        <footer className={s.cardFoot}>
          <span className={s.about}>
            About {insight.methodId}{method ? ` · ${method.name}` : ''}
          </span>
          {method && (
            <Link href={`/sera/methods/${encodeURIComponent(method.id)}`} className="icon-btn sm"
              data-seen-click="true"
              aria-label={`Open ${method.id}, ${method.name}`} data-tip={`Open ${method.id}`}>
              <ArrowUpRight size={18} strokeWidth={1.5} />
            </Link>
          )}
        </footer>
      )}
    </article>
  );
}

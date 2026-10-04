import { ArrowUpRight, Database, ExternalLink, GitBranch } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';
import { PageHeader } from '@/components/sera/PageHeader';
import { Section } from '@/components/sera/Section';
import { requireSera } from '@/lib/sera/gate';
import { lab, methodById } from '@/lib/sera/lab';
import type { LabMethod } from '@/lib/sera/types';
import { methodsWithStatus, needs, readingList, sourceLabel, sourceLink, urlParts, type ReadingLink } from './view';
import s from './ideas.module.css';

export const metadata: Metadata = { title: 'Ideas' };

const methodHref = (id: string) => `/sera/methods/${encodeURIComponent(id)}`;

export default async function IdeasPage() {
  await requireSera('/sera/ideas');
  const backlog = methodsWithStatus(lab.methods, 'idea');
  const blocked = methodsWithStatus(lab.methods, 'blocked-data');
  const reading = readingList(lab.ideasSeen);
  const read = reading.links.length + reading.conceptCount;

  return (
    <>
      <PageHeader
        eyebrow="Ideas"
        title="What comes next"
        lede="What the lab plans to try next, what it cannot try until it has more data, and everything it has already looked at so it never tries the same thing twice."
        asOf={lab.asOf}
      />
      <div className={s.page}>
        <div className={s.tally}>
          <span className="chip num">{backlog.length} waiting</span>
          <span className="chip num">{blocked.length} blocked on data</span>
          <span className="chip num">{reading.links.length} links read</span>
          <span className="chip num">{reading.conceptCount} concepts tried</span>
        </div>

        <div id="backlog">
          <Section
            eyebrow={`Backlog · ${backlog.length}`}
            title="Waiting to be tried"
            caption="Methods written down but not run yet. Each one states its idea and what could go wrong before any result exists."
          >
            {backlog.length === 0 ? (
              <p className={s.empty}>The backlog is empty. The next exploration run will add to it.</p>
            ) : (
              <div className={s.cards}>{backlog.map(m => <IdeaCard key={m.id} method={m} />)}</div>
            )}
          </Section>
        </div>

        <div id="blocked">
          <Section
            eyebrow={`Blocked on data · ${blocked.length}`}
            title="Data wishlist"
            caption="Ideas the lab cannot test with the data it has. Each one says what it needs, so getting that data would unlock it."
          >
            {blocked.length === 0 ? (
              <p className={s.empty}>No idea is waiting on data yet. When one is, it shows here with what it needs.</p>
            ) : (
              <ul className={s.wishes}>{blocked.map(m => <WishRow key={m.id} method={m} />)}</ul>
            )}
            <div className={s.more}>
              <span>More data wishes are in the journal.</span>
              <Link href="/sera/journal?kind=data-wish" className="icon-btn sm"
                aria-label="Open the data wishes in the journal" data-tip="Data wishes in the journal">
                <Database size={18} strokeWidth={1.5} />
              </Link>
            </div>
          </Section>
        </div>

        <div id="reading">
          <Section
            eyebrow={`Reading list · ${read}`}
            title="Everything already looked at"
            caption="Every paper, post and concept the lab has considered, and the method it led to. Hover a tag to read its note."
          >
            <h3 className={s.subhead}>Links · {reading.links.length}</h3>
            {reading.links.length === 0 ? (
              <p className={s.empty}>No link has been read yet.</p>
            ) : (
              <ul className={s.links}>{reading.links.map(l => <LinkRow key={l.key} link={l} />)}</ul>
            )}

            <h3 className={s.subhead}>Concepts · {reading.conceptCount}</h3>
            {reading.groups.length === 0 ? (
              <p className={s.empty}>No concept has been tried yet.</p>
            ) : (
              <div className={s.groups}>
                {reading.groups.map(g => {
                  const m = g.methodId ? methodById(g.methodId) : undefined;
                  return (
                    <div key={g.methodId ?? 'none'} className={s.group}>
                      <div className={s.groupHead}>
                        <span>{g.methodId ? `${g.methodId}${m ? ` · ${m.name}` : ''}` : 'Not tied to a method'}</span>
                        {m && (
                          <Link href={methodHref(m.id)} className="icon-btn sm"
                            aria-label={`Open ${m.id}, ${m.name}`} data-tip={`Open ${m.id}`}>
                            <ArrowUpRight size={18} strokeWidth={1.5} />
                          </Link>
                        )}
                      </div>
                      <ul className={s.tags}>
                        {g.concepts.map(c => (
                          <li key={c.key} className={`chip ${s.tag}`} data-tip={c.note || 'No note'}>
                            {c.label}
                            {c.note && <span className={s.sr}>: {c.note}</span>}
                          </li>
                        ))}
                      </ul>
                    </div>
                  );
                })}
              </div>
            )}
          </Section>
        </div>
      </div>
    </>
  );
}

function IdeaCard({ method: m }: { method: LabMethod }) {
  const parent = m.parentId ? methodById(m.parentId) : undefined;
  const link = sourceLink(m.sourceRef);
  return (
    <article className={`${s.card} bg-butter`}>
      <header className={s.cardHead}>
        <div className={s.cardTitles}>
          <span className={s.cardId}>{m.id}</span>
          <h3 className={s.cardTitle}>{m.name}</h3>
        </div>
        <Link href={methodHref(m.id)} className="icon-btn sm" aria-label={`Open ${m.id}, ${m.name}`} data-tip={`Open ${m.id}`}>
          <ArrowUpRight size={18} strokeWidth={1.5} />
        </Link>
      </header>
      <div className={s.chips}>
        <span className="chip">{m.family}</span>
        <span className="chip">{sourceLabel(m.sourceKind)}</span>
      </div>
      <p className={s.text}>{m.hypothesis}</p>
      {m.expectedFailure && (
        <p className={s.risk}><span className={s.label}>What could go wrong</span>{m.expectedFailure}</p>
      )}
      {(m.sourceRef.trim() || m.parentId) && (
        <footer className={s.cardFoot}>
          {m.sourceRef.trim() && (
            <div className={s.ref}>
              <span className={s.refText}>{link ? urlParts(link).display : m.sourceRef}</span>
              {link && (
                <a href={link} target="_blank" rel="noopener noreferrer" className="icon-btn sm"
                  aria-label="Open the source in a new tab" data-tip="Open the source">
                  <ExternalLink size={17} strokeWidth={1.5} />
                </a>
              )}
            </div>
          )}
          {m.parentId && (
            <div className={s.ref}>
              <span className={s.refText}>Builds on {m.parentId}{parent ? ` · ${parent.name}` : ''}</span>
              {parent && (
                <Link href={methodHref(parent.id)} className="icon-btn sm"
                  aria-label={`Open the parent method ${parent.id}, ${parent.name}`} data-tip={`Parent: ${parent.id}`}>
                  <GitBranch size={17} strokeWidth={1.5} />
                </Link>
              )}
            </div>
          )}
        </footer>
      )}
    </article>
  );
}

function WishRow({ method: m }: { method: LabMethod }) {
  return (
    <li className={s.wish}>
      <div className={s.wishMain}>
        <div className={s.wishHead}>
          <span className={s.cardId}>{m.id}</span>
          <span className={s.wishName}>{m.name}</span>
          <span className={`chip ${s.needs}`}>{needs(m.blockedOn)}</span>
        </div>
        <p className={s.text}>{m.hypothesis}</p>
      </div>
      <Link href={methodHref(m.id)} className="icon-btn sm" aria-label={`Open ${m.id}, ${m.name}`} data-tip={`Open ${m.id}`}>
        <ArrowUpRight size={18} strokeWidth={1.5} />
      </Link>
    </li>
  );
}

function LinkRow({ link: l }: { link: ReadingLink }) {
  const m = l.methodId ? methodById(l.methodId) : undefined;
  return (
    <li className={s.link}>
      <div className={s.linkMain}>
        <span className={s.linkText}>{l.display}</span>
        {l.note && <span className={s.linkNote}>{l.note}</span>}
        {l.methodId && <span className={s.linkNote}>Led to {l.methodId}{m ? ` · ${m.name}` : ''}</span>}
      </div>
      {m && (
        <Link href={methodHref(m.id)} className="icon-btn sm" aria-label={`Open ${m.id}, ${m.name}`} data-tip={`Open ${m.id}`}>
          <ArrowUpRight size={18} strokeWidth={1.5} />
        </Link>
      )}
      {l.safe && (
        <a href={l.url} target="_blank" rel="noopener noreferrer" className="icon-btn sm"
          aria-label={`Open ${l.host} in a new tab`} data-tip={`Open ${l.host}`}>
          <ExternalLink size={17} strokeWidth={1.5} />
        </a>
      )}
    </li>
  );
}

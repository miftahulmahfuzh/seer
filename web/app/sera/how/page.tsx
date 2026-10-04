import { Anchor, ArrowUpRight, Ban, Database, Eye, Hash, Lock, PenLine, type LucideIcon } from 'lucide-react';
import type { Metadata } from 'next';
import Link from 'next/link';
import type { ReactNode } from 'react';
import { Pipeline } from '@/components/sera/diagrams/Pipeline';
import { Windows } from '@/components/sera/diagrams/Windows';
import { PageHeader } from '@/components/sera/PageHeader';
import { Section } from '@/components/sera/Section';
import { Term } from '@/components/sera/Term';
import { requireSera } from '@/lib/sera/gate';
import { GLOSSARY, GLOSSARY_ORDER, type GlossaryKey } from '@/lib/sera/glossary';
import { lab } from '@/lib/sera/lab';
import { dataFacts, honestyRules, hurdles, pipelineLabel, pipelineStages, windowsModel, type Rule } from './view';
import s from './how.module.css';

export const metadata: Metadata = { title: 'How it works' };

const RULE_ICON: Record<Rule['key'], LucideIcon> = {
  counted: Hash,
  first: PenLine,
  reroll: Ban,
  append: Lock,
  look: Eye,
  bar: Anchor,
};

/** A glossary term: the definition comes from lib/sera/glossary (Term itself takes plain strings). */
function T({ k, children }: { k: GlossaryKey; children?: ReactNode }) {
  return <Term term={GLOSSARY[k].term} definition={GLOSSARY[k].plain}>{children}</Term>;
}

export default async function HowPage() {
  await requireSera('/sera/how');
  const stages = pipelineStages(lab);
  const win = windowsModel(lab);
  const hs = hurdles(lab.gate, lab.summary.devTrials);
  const rules = honestyRules(lab);
  const facts = dataFacts(lab.data, lab.gate);
  const wishes = lab.insights.filter(i => i.kind === 'data-wish').length;
  const blocked = lab.methods.filter(m => m.status === 'blocked-data').length;

  return (
    <>
      <PageHeader
        eyebrow="How it works"
        title="How the lab decides"
        lede="How an idea becomes a method, how it is tested, and the rules that stop the lab from fooling itself."
        asOf={lab.asOf}
      />
      <div className={s.page}>
        <Section
          eyebrow="The path"
          title="From idea to real money"
          caption={
            <>
              Each box is a stage, and its pill shows how many methods or tries are there now. Red dashed arrows are
              fails: the lesson goes in the journal and the lab moves to the next idea. Testing starts on
              the <T k="devWindow">dev window</T> and ends with <T k="paperTrading">paper trading</T>.
            </>
          }
        >
          <div className={s.diagram}>
            <Pipeline stages={stages} failLabel="fails → written in the journal, then the next idea"
              label={pipelineLabel(stages)} />
          </div>
        </Section>

        <Section
          eyebrow="The calendar"
          title="Which years are used for what"
          caption={
            <>
              Every idea is built and tested on the practice years. The <T k="testWindow">exam years</T> stay
              sealed for one final look. Red shading marks the two big crashes the practice years include.
            </>
          }
        >
          <div className={s.diagram}>
            <Windows {...win} />
          </div>
        </Section>

        <Section
          eyebrow="The hurdles"
          title="Six things every method must clear"
          caption="A method passes the practice stage only if one of its variants clears all six at once. The numbers come from the lab’s own settings."
        >
          <div className={s.grid3}>
            {hs.map((h, i) => (
              <article key={h.key} className={s.card}>
                <div className={s.cardHead}>
                  <span className={s.idx}>{String(i + 1).padStart(2, '0')}</span>
                </div>
                <h3 className={s.cardTitle}><T k={h.term}>{h.title}</T></h3>
                <span className={`chip num ${s.target}`}>{h.target}</span>
                <p className={s.plain}>{h.plain}</p>
              </article>
            ))}
          </div>
        </Section>

        <Section
          eyebrow="The honesty rules"
          title="Why a pass here means something"
          caption={
            <>
              Test enough ideas on the same past and one will look brilliant by luck. These rules, and counting
              every try (<T k="tries">N</T>), stop the lab from fooling itself.
            </>
          }
        >
          <ul className={s.rules}>
            {rules.map(r => {
              const Icon = RULE_ICON[r.key];
              return (
                <li key={r.key} className={s.rule}>
                  <span className={s.ruleIcon} aria-hidden="true"><Icon size={20} strokeWidth={1.6} /></span>
                  <div className={s.ruleText}>
                    <h3 className={s.ruleTitle}>{r.title}</h3>
                    <p className={s.plain}>{r.body}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        </Section>

        <Section
          eyebrow="The data"
          title="What the lab can see, and what it cannot"
          caption="Every method is limited to the data on the left. Ideas that need something on the right wait as data wishes."
        >
          <div className={s.cols}>
            <div className={`${s.col} bg-sky`}>
              <div className={s.colHead}><h3 className={s.colTitle}>What it has</h3></div>
              <ul className={s.facts}>
                {facts.has.map(f => (
                  <li key={f.key} className={s.fact}>
                    <span className={s.factTitle}>{f.title}</span>
                    <span className={s.factBody}>{f.body}</span>
                  </li>
                ))}
              </ul>
            </div>
            <div className={`${s.col} bg-butter`}>
              <div className={s.colHead}>
                <h3 className={s.colTitle}>What it lacks</h3>
                <div className={s.links}>
                  <Link href="/sera/journal?kind=data-wish" className="icon-btn sm"
                    aria-label={`Open the ${wishes} data wishes in the journal`} data-tip={`Data wishes · ${wishes}`}>
                    <Database size={18} strokeWidth={1.5} />
                  </Link>
                  <Link href="/sera/ideas#blocked" className="icon-btn sm"
                    aria-label={`Open the ${blocked} ideas blocked on data`} data-tip={`Blocked on data · ${blocked}`}>
                    <ArrowUpRight size={18} strokeWidth={1.5} />
                  </Link>
                </div>
              </div>
              <ul className={s.facts}>
                {facts.lacks.map(f => (
                  <li key={f.key} className={s.fact}>
                    <span className={s.factTitle}>{f.title}</span>
                    <span className={s.factBody}>{f.body}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </Section>

        <Section
          eyebrow="The words"
          title="Glossary"
          caption="The plain meaning of every term used across Sera. Hover an underlined word anywhere for the same text."
        >
          <dl className={s.glossary}>
            {GLOSSARY_ORDER.map(k => (
              <div key={k} style={{ display: 'contents' }}>
                <dt>{GLOSSARY[k].term}</dt>
                <dd>{GLOSSARY[k].plain}</dd>
              </div>
            ))}
          </dl>
        </Section>
      </div>
    </>
  );
}

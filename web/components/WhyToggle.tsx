'use client';

import { ChevronDown, ChevronUp } from 'lucide-react';
import { useState } from 'react';
import { whyContent } from '@/lib/why';
import s from './WhyToggle.module.css';

/**
 * "Why this pick", collapsed by default. Shows the LLM's plain-language explanation when there is
 * one; else the facts the method used for the pick (`orders.evidence` and friends), as a short list;
 * else `missing`. `label` and `missing` let other plain-language reasons (the news check's verdicts,
 * "would pick now") reuse it unchanged.
 */
export function WhyToggle({ text, facts = null, label = 'Why this pick', missing = 'Explanation unavailable for this pick.' }: {
  text: string | null;
  facts?: readonly string[] | null;
  label?: string;
  missing?: string;
}) {
  const [open, setOpen] = useState(false);
  const tip = open ? 'Hide explanation' : label;
  const why = whyContent(text, facts, missing);
  return (
    <>
      <div className={s.row}>
        <button type="button" className={`icon-btn sm ${open ? 'inverted' : 'soft'}`} data-tip={tip} aria-label={tip}
          aria-expanded={open} onClick={() => setOpen(o => !o)}>
          {open ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
        </button>
        <span className={s.label}>{label}</span>
      </div>
      {open && (why.kind === 'facts' ? (
        <ul className={s.facts}>
          {why.facts.map((f, i) => <li key={i}>{f}</li>)}
        </ul>
      ) : (
        <p className={s.why}>{why.text}</p>
      ))}
    </>
  );
}

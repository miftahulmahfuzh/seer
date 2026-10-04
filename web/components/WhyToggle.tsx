'use client';

import { ChevronDown, ChevronUp } from 'lucide-react';
import { useState } from 'react';
import s from './WhyToggle.module.css';

/**
 * "Why this pick": the LLM's plain-language explanation, collapsed by default. `label` and
 * `missing` let other plain-language reasons (the news check's verdicts) reuse it unchanged.
 */
export function WhyToggle({ text, label = 'Why this pick', missing = 'Explanation unavailable for this pick.' }: {
  text: string | null;
  label?: string;
  missing?: string;
}) {
  const [open, setOpen] = useState(false);
  const tip = open ? 'Hide explanation' : label;
  return (
    <>
      <div className={s.row}>
        <button type="button" className={`icon-btn sm ${open ? 'inverted' : 'soft'}`} data-tip={tip} aria-label={tip}
          aria-expanded={open} onClick={() => setOpen(o => !o)}>
          {open ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
        </button>
        <span className={s.label}>{label}</span>
      </div>
      {open && <p className={s.why}>{text ?? missing}</p>}
    </>
  );
}

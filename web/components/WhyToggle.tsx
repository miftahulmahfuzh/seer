'use client';

import { ChevronDown, ChevronUp } from 'lucide-react';
import { useState } from 'react';
import s from './WhyToggle.module.css';

/** "Why this pick": the LLM's plain-language explanation, collapsed by default. */
export function WhyToggle({ text }: { text: string | null }) {
  const [open, setOpen] = useState(false);
  const tip = open ? 'Hide explanation' : 'Why this pick';
  return (
    <>
      <div className={s.row}>
        <button type="button" className={`icon-btn sm ${open ? 'inverted' : 'soft'}`} data-tip={tip} aria-label={tip}
          aria-expanded={open} onClick={() => setOpen(o => !o)}>
          {open ? <ChevronUp size={20} /> : <ChevronDown size={20} />}
        </button>
        <span className={s.label}>Why this pick</span>
      </div>
      {open && <p className={s.why}>{text ?? 'Explanation unavailable for this pick.'}</p>}
    </>
  );
}

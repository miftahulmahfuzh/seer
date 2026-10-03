'use client';

import { Check, Copy } from 'lucide-react';
import { useRef, useState } from 'react';
import { hideTip, showTip } from './tooltip';

/** Copies a bare value (e.g. "271.40") for pasting into the Gotrade ticket. */
export function CopyButton({ value, tip }: { value: string; tip: string }) {
  const [copied, setCopied] = useState(false);
  const ref = useRef<HTMLButtonElement>(null);

  const copy = () => {
    navigator.clipboard?.writeText(value).catch(() => {});
    setCopied(true);
    if (ref.current) showTip(ref.current, `Copied ${value}`);
    setTimeout(() => { setCopied(false); hideTip(); }, 1400);
  };

  return (
    <button ref={ref} type="button" className="icon-btn sm solid" data-tip={tip} aria-label={tip} onClick={copy}>
      {copied ? <Check size={18} strokeWidth={1.6} /> : <Copy size={18} strokeWidth={1.6} />}
    </button>
  );
}

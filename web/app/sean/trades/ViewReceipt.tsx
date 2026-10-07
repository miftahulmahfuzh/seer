'use client';

import { Image as ImageIcon, LoaderCircle, X } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { SCREENSHOT_CLOSE, SCREENSHOT_LOADING, SCREENSHOT_MISSING } from './view';
import s from './trades.module.css';

type Shown = 'loading' | 'shown' | 'missing';

/**
 * The picture icon opens the original Order Summary screenshot the order was read from, full
 * size, in a modal dialog (Esc, the X, or a click outside the picture closes it). The image is
 * only requested once the dialog opens.
 */
export function ViewReceipt({ id, label }: { id: number; label: string }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [open, setOpen] = useState(false);
  const [shown, setShown] = useState<Shown>('loading');

  useEffect(() => {
    const d = dialog.current;
    if (!d) return;
    if (open && !d.open) d.showModal();
    if (!open && d.open) d.close();
  }, [open]);

  return (
    <>
      <button type="button" className="icon-btn sm" onClick={() => { setShown('loading'); setOpen(true); }}
        aria-label={label} data-tip={label}>
        <ImageIcon size={18} strokeWidth={1.5} />
      </button>
      <dialog ref={dialog} className={s.shot} aria-label={label} onClose={() => setOpen(false)}
        onClick={e => { if (e.target === e.currentTarget) setOpen(false); }}>
        <button type="button" className={`icon-btn sm ${s.shotClose}`} onClick={() => setOpen(false)}
          aria-label={SCREENSHOT_CLOSE} data-tip={SCREENSHOT_CLOSE}>
          <X size={18} strokeWidth={1.5} />
        </button>
        {open && (
          <>
            {shown === 'loading' && (
              <p className={s.shotNote} role="status">
                <LoaderCircle size={18} strokeWidth={1.75} className={s.spin} /> {SCREENSHOT_LOADING}
              </p>
            )}
            {shown === 'missing' && <p className={s.shotNote} role="status">{SCREENSHOT_MISSING}</p>}
            {/* eslint-disable-next-line @next/next/no-img-element -- an owner-only API image, not a static asset */}
            <img
              src={`/api/sean/orders/${id}/image`}
              alt={label.replace(/^See the /, 'The ')}
              className={s.shotImg}
              hidden={shown !== 'shown'}
              onLoad={() => setShown('shown')}
              onError={() => setShown('missing')}
            />
          </>
        )}
      </dialog>
    </>
  );
}

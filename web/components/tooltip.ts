// Tooltips for icon-only controls: hover on desktop, long-press on touch.
// Any element with data-tip. Ported from docs/design/seer-ui.js.

let tip: HTMLDivElement | null = null;
let hideTimer: ReturnType<typeof setTimeout> | undefined;

export function showTip(el: Element, text?: string) {
  const t = text ?? el.getAttribute('data-tip');
  if (!t) return;
  if (!tip) {
    tip = document.createElement('div');
    tip.setAttribute('role', 'tooltip');
    document.body.appendChild(tip);
  }
  clearTimeout(hideTimer);
  const cs = getComputedStyle(el);
  // Short captions stay one-line pills. Longer ones (Sera's glossary terms, chart points) wrap in a
  // rounded box; a '\n' in the text forces a line break.
  const multi = t.includes('\n');
  const long = multi || t.length > 48;
  Object.assign(tip.style, {
    position: 'fixed', zIndex: '9999', pointerEvents: 'none', left: '0px', top: '0px',
    background: cs.getPropertyValue('--ink').trim() || '#1d1c1a',
    color: cs.getPropertyValue('--sheet').trim() || '#ffffff',
    font: `500 13px/${long ? '1.4' : '1.2'} var(--font-outfit), system-ui, sans-serif`, letterSpacing: '0.01em',
    padding: long ? '10px 14px' : '9px 14px', borderRadius: long ? '16px' : '999px',
    whiteSpace: multi ? 'pre-line' : long ? 'normal' : 'nowrap', maxWidth: long ? '340px' : 'none',
    opacity: '1', transition: 'opacity .12s',
  });
  tip.textContent = t;
  // Inside a [data-tip-anchor] (the mobile tab bar) the caption clears the whole container, not just the tab.
  const box = el.closest('[data-tip-anchor]');
  const r = el.getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight;
  const x = Math.max(6, Math.min(innerWidth - w - 6, r.left + r.width / 2 - w / 2));
  let y = box ? box.getBoundingClientRect().top - h - 10 : r.top - h - 8;
  if (y < 6) y = r.bottom + 8;
  tip.style.left = x + 'px';
  tip.style.top = y + 'px';
}

export function hideTip(after = 0) {
  clearTimeout(hideTimer);
  hideTimer = setTimeout(() => { if (tip) tip.style.opacity = '0'; }, after);
}

/** Installs document listeners once; returns an uninstaller. */
export function installTooltips(): () => void {
  let timer: ReturnType<typeof setTimeout> | undefined;
  let longPressed = false;
  const target = (e: Event) => (e.target as Element | null)?.closest?.('[data-tip]') ?? null;

  const over = (e: Event) => { const el = target(e); if (el) showTip(el); else hideTip(); };
  const start = (e: Event) => {
    const el = target(e); if (!el) return;
    longPressed = false; clearTimeout(timer);
    timer = setTimeout(() => { longPressed = true; showTip(el); }, 450);
  };
  const move = () => clearTimeout(timer);
  const end = () => { clearTimeout(timer); if (longPressed) hideTip(1400); };
  const menu = (e: Event) => { if (target(e)) e.preventDefault(); };
  // A long-press only shows the tooltip; it must not also fire the button.
  const click = (e: Event) => {
    if (longPressed) { e.preventDefault(); e.stopPropagation(); longPressed = false; }
  };

  document.addEventListener('mouseover', over);
  document.addEventListener('touchstart', start, { passive: true });
  document.addEventListener('touchmove', move, { passive: true });
  document.addEventListener('touchend', end);
  document.addEventListener('contextmenu', menu);
  document.addEventListener('click', click, true);
  return () => {
    document.removeEventListener('mouseover', over);
    document.removeEventListener('touchstart', start);
    document.removeEventListener('touchmove', move);
    document.removeEventListener('touchend', end);
    document.removeEventListener('contextmenu', menu);
    document.removeEventListener('click', click, true);
  };
}

'use client';

import { useEffect, useRef, useState } from 'react';
import type { InsightKind } from '@/lib/sera/types';
// view.ts is pure — it imports only lib/sera/glossary and lib/sera/types, neither of which
// touches lib/db, lib/sera/lab or anything server-only — so a client island may import it.
// badgeTip is the ONE formatter for the seven tab tooltips: the server render calls it, and so
// does the repaint below, which is why the wording cannot fork as the badge counts down.
import { badgeTip } from './view';
import {
  DWELL_MS, FLUSH_IDLE_MS, MAX_BATCH, OBSERVER_THRESHOLDS, SEEN_ENDPOINT,
  badgeCounts, createSeenQueue, isOnScreen, isUnseenAttr, seenRequestBody,
  type BadgeKey, type BadgeMeta, type SeenBatch, type SeenQueue, type SeenVia,
} from './seen-client';

export type JournalSeenProps = {
  /** The ids the server still calls unseen, per kind, as of this render. Integers only. */
  unseenByKind: Record<InsightKind, number[]>;
  /** Per tab, the heading and the total — badgeTip's other two arguments. From page.tsx's options. */
  badgeMeta: BadgeMeta;
  /** `journal.module.css`'s hashed `zero` class, so the island can mute a badge that hits zero. */
  zeroClass: string;
};

const idOf = (el: Element): number => Number(el.getAttribute('data-insight-id'));
const usable = (id: number): boolean => Number.isInteger(id) && id > 0;

/**
 * Marks Journal entries seen, and counts the seven badges down while the reader reads.
 *
 * Two rules, both of them R2's answer: a click on a card's redirect-arrow (`data-seen-click`), and
 * a continuous DWELL_MS of the card being on screen in a visible tab — the second being the only
 * thing that can ever mark the five entries in the snapshot that carry no methodId and therefore
 * have no arrow.
 *
 * It renders nothing. The page stays a server component; this island only reads the hooks phase 3
 * put in the DOM, posts ids to phase 1's endpoint, and repaints seven numbers. It never moves a
 * card (plan invariant 5) and it never surfaces a failure to the reader.
 */
export function JournalSeen({ unseenByKind, badgeMeta, zeroClass }: JournalSeenProps) {
  // One queue for the life of the island: it survives a tab switch, so an id marked before the
  // switch stays off the badges even though the server has not been told yet.
  const queueRef = useRef<SeenQueue | null>(null);
  if (queueRef.current === null) queueRef.current = createSeenQueue(MAX_BATCH);

  // Latest props, readable from callbacks that are not re-created on every render.
  const unseenRef = useRef(unseenByKind);
  unseenRef.current = unseenByKind;
  const metaRef = useRef(badgeMeta);
  metaRef.current = badgeMeta;
  const zeroRef = useRef(zeroClass);
  zeroRef.current = zeroClass;

  // Bumped whenever an id is marked, purely to make React commit so the paint effect runs again.
  const [, setTick] = useState(0);

  // A content key. The prop object is a fresh identity every render, so an effect depending on it
  // would tear down and rebuild the observer constantly; the string only changes when the server's
  // unseen set actually changes — first load, and a tab switch.
  const unseenKey = JSON.stringify(unseenByKind);

  // --- paint ---------------------------------------------------------------
  // No dependency array on purpose. React re-renders this bar on a soft navigation and writes the
  // server's numbers back over the patched ones, so the countdown has to be re-applied after every
  // commit. badgeCounts() never subtracts from a base, so re-applying can never double-count.
  useEffect(() => {
    const marked = queueRef.current!.marked();
    const counts = badgeCounts(unseenRef.current, marked);
    const meta = metaRef.current;
    const zero = zeroRef.current;

    for (const el of Array.from(document.querySelectorAll<HTMLElement>('[data-badge-kind]'))) {
      const key = el.dataset.badgeKind as BadgeKey | undefined;
      if (!key || !(key in counts)) continue;
      const n = counts[key];
      const text = String(n);
      if (el.textContent !== text) el.textContent = text;
      if (zero) el.classList.toggle(zero, n === 0);

      // Keep the tooltip and the accessible name honest by calling view.ts's badgeTip again —
      // the same function page.tsx used for the server render, so the wording cannot fork. The
      // heading and the total come from the page's own `options`, handed over as badgeMeta.
      // tooltip.ts reads data-tip at show time, so rewriting the attribute is enough.
      const m = meta[key];
      const link = el.closest<HTMLElement>('a[data-tip]');
      if (m && link) {
        const tip = badgeTip(m.heading, n, m.total);
        if (link.getAttribute('data-tip') !== tip) {
          link.setAttribute('data-tip', tip);
          link.setAttribute('aria-label', tip);
        }
      }
    }

    // The per-card marker. The card keeps its slot — only its state changes (invariant 5).
    // Both attributes, deliberately: data-unseen="false" is what isUnseenAttr and phase 3's
    // .card[data-unseen='true'] rule read, and data-seen-now is what keeps phase 3's dot in the
    // layout while it fades to opacity 0, so retiring a marker never reflows the title beside it.
    // Write "false" rather than removing the attribute — the island and the server must agree on
    // one spelling, and an absent attribute is a second one.
    for (const id of marked) {
      const card = document.querySelector<HTMLElement>(`[data-insight-id="${id}"]`);
      if (!card) continue;
      if (card.getAttribute('data-unseen') !== 'false') card.setAttribute('data-unseen', 'false');
      if (!card.hasAttribute('data-seen-now')) card.setAttribute('data-seen-now', '');
    }
  });

  // --- wire ----------------------------------------------------------------
  useEffect(() => {
    const queue = queueRef.current!;
    const dwell = new Map<Element, ReturnType<typeof setTimeout>>();
    let idle: ReturnType<typeof setTimeout> | undefined;
    let stopped = false;

    const clearDwell = (el: Element) => {
      const t = dwell.get(el);
      if (t !== undefined) {
        clearTimeout(t);
        dwell.delete(el);
      }
    };
    const clearAllDwell = () => {
      for (const t of dwell.values()) clearTimeout(t);
      dwell.clear();
    };

    // A failed POST is swallowed. The ids go back on the queue for the next flush and the reader
    // is told nothing: this is soft state and a network error over it would be noise.
    const post = (batch: SeenBatch, unloading: boolean) => {
      const body = seenRequestBody(batch);
      if (unloading && typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
        // text/plain because sendBeacon sends a Blob; phase 1's route accepts it for this reason.
        const ok = navigator.sendBeacon(
          SEEN_ENDPOINT,
          new Blob([body], { type: 'text/plain;charset=UTF-8' }),
        );
        if (!ok) queue.requeue([batch]);
        return;
      }
      fetch(SEEN_ENDPOINT, {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body,
        keepalive: unloading,
        cache: 'no-store',
      })
        .then(res => {
          if (!res.ok) queue.requeue([batch]);
        })
        .catch(() => queue.requeue([batch]));
    };

    const flush = (unloading: boolean) => {
      if (idle !== undefined) {
        clearTimeout(idle);
        idle = undefined;
      }
      for (const batch of queue.take()) post(batch, unloading);
    };

    const scheduleFlush = () => {
      if (idle !== undefined) clearTimeout(idle);
      idle = setTimeout(() => {
        idle = undefined;
        flush(false);
      }, FLUSH_IDLE_MS);
    };

    const mark = (id: number, via: SeenVia) => {
      const added = usable(id) && queue.add(id, via);
      if (added) setTick(t => t + 1);
      // A click navigates away, so it beacons immediately — even for an id dwell already marked,
      // whose 'view' entry may still be sitting in the queue.
      if (via === 'click') {
        flush(true);
        return;
      }
      if (!added) return;
      if (queue.isFull()) flush(false);
      else scheduleFlush();
    };

    // --- the dwell rule ---
    const observer = new IntersectionObserver(
      entries => {
        if (stopped) return;
        const visible = document.visibilityState === 'visible';
        for (const e of entries) {
          const el = e.target;
          const viewport = e.rootBounds?.height ?? window.innerHeight;
          const on =
            visible &&
            isOnScreen(e.boundingClientRect, e.isIntersecting ? e.intersectionRect : null, viewport);
          if (!on) {
            clearDwell(el);
            continue;
          }
          if (dwell.has(el)) continue;
          const id = idOf(el);
          if (!usable(id) || queue.has(id)) continue;
          dwell.set(
            el,
            setTimeout(() => {
              dwell.delete(el);
              if (stopped) return;
              // Re-checked here as well: the tab can go hidden between setting and firing.
              if (document.visibilityState !== 'visible') return;
              mark(id, 'view');
              observer.unobserve(el);
            }, DWELL_MS),
          );
        }
      },
      // Spread: IntersectionObserverInit wants a mutable `number[]`, and the constant is readonly.
      { threshold: [...OBSERVER_THRESHOLDS] },
    );

    const targets = Array.from(document.querySelectorAll<HTMLElement>('[data-insight-id]')).filter(
      el => usable(idOf(el)) && isUnseenAttr(el.getAttribute('data-unseen')) && !queue.has(idOf(el)),
    );
    for (const el of targets) observer.observe(el);

    // --- the click rule ---
    // Capture phase, so the id is queued and beaconed before Next's Link handler navigates.
    const onClick = (ev: MouseEvent) => {
      const t = ev.target;
      if (!(t instanceof Element)) return;
      const hook = t.closest('[data-seen-click]');
      if (!hook) return;
      const card = hook.closest('[data-insight-id]');
      if (card) mark(idOf(card), 'click');
    };
    document.addEventListener('click', onClick, true);

    // --- visibility ---
    const onVisibility = () => {
      if (stopped) return;
      if (document.visibilityState === 'visible') {
        // An IntersectionObserver does not re-fire on its own; unobserve + observe delivers a fresh
        // entry with the current geometry, which restarts the dwell for whatever is on screen.
        for (const el of targets) {
          observer.unobserve(el);
          if (!queue.has(idOf(el))) observer.observe(el);
        }
        return;
      }
      // Hidden: a background tab marks nothing. Cancel outright, do not pause — a tab backgrounded
      // at 2.4s and restored a minute later starts its dwell over.
      clearAllDwell();
      flush(true);
    };
    document.addEventListener('visibilitychange', onVisibility);

    const onPageHide = () => {
      clearAllDwell();
      flush(true);
    };
    window.addEventListener('pagehide', onPageHide);

    return () => {
      stopped = true;
      observer.disconnect();
      clearAllDwell();
      if (idle !== undefined) {
        clearTimeout(idle);
        idle = undefined;
      }
      document.removeEventListener('click', onClick, true);
      document.removeEventListener('visibilitychange', onVisibility);
      window.removeEventListener('pagehide', onPageHide);
      // Whatever is still queued when the island goes away is still the reader's; beacon it.
      flush(true);
    };
  }, [unseenKey]);

  return null;
}

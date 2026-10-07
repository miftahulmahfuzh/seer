import { ExternalLink } from 'lucide-react';
import type { ReactNode } from 'react';
import s from './leaderboard.module.css';

/**
 * The picked strategy's name in a sheet's eyebrow. A link to its Sera method page when there is
 * one — a lab-derived entry, read by the one account /sera admits — and the plain name otherwise,
 * which is the ordinary case for C and SPY as much as for anyone but Sera's owner. The caller
 * decides whether there is an href; this only renders what it is given.
 */
export function PickName({ name, href }: { name?: string; href: string | null }): ReactNode {
  if (!name) return '—';
  if (!href) return name;
  return (
    // The label keeps the visible name first so the spoken and the written link still match
    // (WCAG 2.5.3); the rest is the part only the icon says to anyone who can see it.
    <a href={href} target="_blank" rel="noreferrer" className={s.methodLink}
      data-tip="Sera's method page, in a new tab" aria-label={`${name} — Sera's method page, opens in a new tab`}>
      {name}<ExternalLink size={12} strokeWidth={2} aria-hidden="true" />
    </a>
  );
}

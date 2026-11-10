import type { AnchorHTMLAttributes, ReactNode } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';

vi.mock('next/link', () => ({
  default: ({ href, children, replace: _r, scroll: _s, ...rest }:
    AnchorHTMLAttributes<HTMLAnchorElement> & { href: string; replace?: boolean; scroll?: boolean; children?: ReactNode }) =>
    <a href={href} {...rest}>{children}</a>,
}));

import { StrategySwitch } from './StrategySwitch';
import s from './StrategySwitch.module.css';

const roster = (n: number) =>
  Array.from({ length: n }, (_, i) => ({ id: `S${i}`, name: `Strategy ${i}`, icon: 'zap' }));
const navOpen = (html: string) => html.match(/^<nav[^>]*>/)?.[0] ?? '';
const links = (html: string) => html.match(/<a /g)?.length ?? 0;
const href = (id: string) => `/leaderboard?s=${id}`;

describe('StrategySwitch', () => {
  it('default mode: the loose wrapping row, no inline style', () => {
    const html = renderToStaticMarkup(
      <StrategySwitch strategies={roster(7)} current="S0" href={href} label="Strategy" />);
    const nav = navOpen(html);
    expect(nav).not.toContain('style=');
    expect(nav).toContain(`class="${s.group}"`);
    expect(links(html)).toBe(7);
  });

  it('fit: one column per button, the count handed to CSS as --n', () => {
    for (const n of [7, 12]) {
      const html = renderToStaticMarkup(
        <StrategySwitch strategies={roster(n)} current="S1" href={href} label="Strategy" fit />);
      const nav = navOpen(html);
      expect(nav).toContain(`class="${s.fit}"`);
      expect(nav).toContain(`style="--n:${n}"`);
      expect(links(html)).toBe(n);
      // Still icon-only, named and tipped, with the pick marked.
      expect(html).toContain('aria-label="Strategy 1" aria-current="true"');
      expect(html).toContain(`data-tip="Strategy ${n - 1}"`);
    }
  });

  it('fit counts the leading all-strategies button', () => {
    const html = renderToStaticMarkup(
      <StrategySwitch strategies={roster(7)} current="all" href={href} label="Strategy filter" allTip="All strategies" fit />);
    expect(navOpen(html)).toContain('style="--n:8"');
    expect(links(html)).toBe(8);
  });

  it('seg wins over fit: the pill sizes its own buttons', () => {
    const html = renderToStaticMarkup(
      <StrategySwitch strategies={roster(7)} current="S0" href={href} label="Strategy" seg fit />);
    const nav = navOpen(html);
    expect(nav).toContain('class="seg"');
    expect(nav).not.toContain('style=');
  });
});

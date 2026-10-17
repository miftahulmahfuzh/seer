import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { RetiredShelf } from './RetiredShelf';

const card = <a href="/leaderboard?s=RAW-FR-GT">RAW · Unbraked momentum</a>;

describe('RetiredShelf', () => {
  it('is folded by default, with its record still in the page', () => {
    const html = renderToStaticMarkup(<RetiredShelf count={1} cols={6} open={false}>{card}</RetiredShelf>);
    expect(html).toContain('Retired · 1');
    // Folded, not dropped: the card is rendered and hidden, so it stays reachable.
    expect(html).toMatch(/id="retired-cards"[^>]*hidden=""/);
    expect(html).toContain('href="/leaderboard?s=RAW-FR-GT"');
    expect(html).toContain('aria-expanded="false"');
  });

  it('has one control, icon-only, named and tipped by what it does', () => {
    const html = renderToStaticMarkup(<RetiredShelf count={2} cols={6} open={false}>{card}</RetiredShelf>);
    const buttons: string[] = html.match(/<button[^>]*>.*?<\/button>/g) ?? [];
    expect(buttons).toHaveLength(1);
    expect(buttons[0]).toContain('aria-label="Show retired strategies"');
    expect(buttons[0]).toContain('data-tip="Show retired strategies"');
    // Nothing but the icon inside it.
    expect(String(buttons[0]).replace(/<svg.*<\/svg>/, '')).toMatch(/<button[^>]*><\/button>/);
  });

  it('opens when the picked strategy is retired', () => {
    const html = renderToStaticMarkup(<RetiredShelf count={1} cols={6} open>{card}</RetiredShelf>);
    expect(html).not.toMatch(/id="retired-cards"[^>]*hidden/);
    expect(html).toContain('aria-label="Hide retired strategies"');
    expect(html).toContain('aria-expanded="true"');
  });
});

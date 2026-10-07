import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { PickName } from './PickName';

const NAME = 'RAW · Unbraked momentum';

describe('PickName', () => {
  it('links the strategy name to its method page in a new tab', () => {
    const html = renderToStaticMarkup(<PickName name={NAME} href="/sera/methods/M0007" />);
    expect(html).toContain('href="/sera/methods/M0007"');
    expect(html).toContain('target="_blank"');
    // `target="_blank"` without this leaves the new tab holding a handle on this one.
    expect(html).toContain('rel="noreferrer"');
    expect(html).toContain(NAME);
    // The icon is decoration; the name carries the meaning.
    expect(html).toContain('aria-hidden="true"');
  });

  it('names the link by what it says, then where it goes', () => {
    const html = renderToStaticMarkup(<PickName name={NAME} href="/sera/methods/M0007" />);
    const label = /aria-label="([^"]*)"/.exec(html)?.[1] ?? '';
    // WCAG 2.5.3: the accessible name starts with the visible text, so saying the link aloud
    // and reading it off the screen agree.
    expect(label.startsWith(NAME)).toBe(true);
    expect(label).toContain('new tab');
  });

  it('renders the plain name when there is no method page', () => {
    // C and SPY have no lab method, and no one but Sera's owner may open /sera: in both cases
    // the eyebrow must read exactly as it did before, with nothing to click.
    const html = renderToStaticMarkup(<PickName name="C · Hold the market" href={null} />);
    expect(html).toBe('C · Hold the market');
    expect(html).not.toContain('<a');
  });

  it('falls back to the dash when nothing is picked', () => {
    expect(renderToStaticMarkup(<PickName name={undefined} href={null} />)).toBe('—');
    // An href with no name is still nothing to link: the dash is not a strategy.
    expect(renderToStaticMarkup(<PickName name={undefined} href="/sera/methods/M0007" />)).toBe('—');
  });
});
